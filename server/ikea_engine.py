from multiprocessing import Process, Pipe
import http_server

import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
import ikea_pb2
import sys
import os
import cv2
import credentials

faster_rcnn_root = os.getenv('FASTER_RCNN_ROOT', '.')
sys.path.append(os.path.join(faster_rcnn_root, "tools"))
import _init_paths  # this is necessary
from fast_rcnn.config import cfg as faster_rcnn_config
from fast_rcnn.test import im_detect
from fast_rcnn.nms_wrapper import nms
sys.path.append(os.path.join(faster_rcnn_root, "python"))
import caffe

import cv_rules


PROTOTXT = 'model/faster_rcnn_test.pt'
CAFFEMODEL = 'model/model.caffemodel'

# Max image width and height
IMAGE_MAX_WH = 640

CONF_THRESH = 0.5
NMS_THRESH = 0.3

IMAGE_DIR = 'images'

DUMMY_IMG_SIZE = (300, 500, 3)

CLASS_IDX_LIMIT = cv_rules.BULB + 1  # Bulb has the highest index

if not os.path.isfile(CAFFEMODEL):
    raise IOError(('{:s} not found.').format(CAFFEMODEL))


faster_rcnn_config.TEST.HAS_RPN = True  # Use RPN for proposals

logger = logging.getLogger(__name__)


PROTO_TO_STATE = {state.get_proto_step: state for state in cv_rules.State}


class IkeaEngine(cognitive_engine.Engine):
    def __init__(self):
        http_server_conn, self._engine_conn = Pipe()
        self._http_server_process = Process(
            target=http_server.start_http_server,
            args=(http_server_conn,))
        self._http_server_process.start()

        caffe.set_mode_gpu()

        # 0 is the default GPU ID
        caffe.set_device(0)
        faster_rcnn_config.GPU_ID = 0

        self.net = caffe.Net(PROTOTXT, CAFFEMODEL, caffe.TEST)
        # Warmup on a dummy image
        img = 128 * np.ones(DUMMY_IMG_SIZE, dtype=np.uint8)
        for i in range(2):
            _, _ = im_detect(self.net, img)
        logger.info('Caffe net has been initilized')

    def _detect_objects(self, img):
        scores, boxes = im_detect(self.net, img)

        dets_for_class = {}
        # Start from 1 because 0 is the background
        for cls_idx in range(1, CLASS_IDX_LIMIT):
            cls_boxes = boxes[:, 4 * cls_idx : 4 * (cls_idx + 1)]
            cls_scores = scores[:, cls_idx]

            # dets: detected results, each line is in
            #       [x1, y1, x2, y2, confidence] format
            dets = np.hstack((cls_boxes, cls_scores[:, np.newaxis])).astype(
                np.float32)

            # non maximum suppression
            keep = nms(dets, NMS_THRESH)
            dets = dets[keep, :]

            dets_for_class[cls_idx] = [
                det for det in dets if det[-1] >= CONF_THRESH
            ]

        return dets_for_class

    def handle(self, input_frame):
        to_server_extras = cognitive_engine.unpack_extras(
            ikea_pb2.ToServerExtras, input_frame)

        # When State contains a oneof field for different tasks, we can see if
        # none have been set using to_server_extras.WhichOneof('')

        if to_server_extras.state.step == ikea_pb2.State.Step.DONE:
            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            return cognitive_engine.create_result_wrapper(status)
        elif to_server_extras.state.step == ikea_pb2.State.Step.START:
            return State.BASE.create_result_wrapper(update_count=0)

        state = PROTO_TO_STATE[to_server_extras.state.step]
        if (to_server_extras.zoom_status ==
            ikea_pb2.ToServerExtras.ZoomStatus.START):
            msg = {
                'zoom_action': 'start',
                'state': state.name.lower()
            }
            self._engine_conn.send(msg)
            logger.info('Zoom Started')

            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)

            to_client_extras = sandwich_pb2.ToClientExtras()
            to_client_extras.zoom_info.app_key = credentials.ANDROID_KEY
            to_client_extras.zoom_info.app_secret = credentials.ANDROID_SECRET
            to_client_extras.zoom_info.meeting_number = (
                credentials.MEETING_NUMBER)
            to_client_extras.zoom_info.meeting_password = (
                credentials.MEETING_PASSWORD)

            result_wrapper.extras.Pack(to_client_extras)
            return result_wrapper
        elif (to_server_extras.zoom_status ==
              sandwich_pb2.ToServer.ZoomStatus.STOP):
            msg = {
                'zoom_action': 'stop'
            }
            self._engine_conn.send(msg)
            pipe_output = self._engine_conn.recv()
            new_state_name = pipe_output.get('state')
            logger.info('Zoom Stopped. New state: %s', new_state_name)
            state = cv_rules.State[new_state_name.upper()]
            return state.create_result_wrapper(update_count=0)

        assert len(input_frame.payloads) == 1
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            return cognitive_engine.create_result_wrapper(status)

        np_data = np.frombuffer(input_frame.payloads[0], dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if max(img.shape) > IMAGE_MAX_WH:
            raise Exception('Image too large')

        return self._result_wrapper_from_cv(img, state)

    def _result_wrapper_from_cv(self, img, old_state):
        dets_for_class = self._detect_objects(img)

        if old_state == cv_rules.State.BASE:
            return cv_rules.base_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.PIPE:
            return cv_rules.pipe_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.SHADE:
            return cv_rules.shade_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.BUCKLE:
            return cv_rules.buckle_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.BLACKCIRCLE:
            return cv_rules.blackcircle_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.LAMP:
            return cv_rules.lamp_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.BULB:
            return cv_rules.bulb_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.BULBTOP:
            return cv_rules.bulbtop_result(dets_for_class, old_state)
        elif old_state == cv_rules.State.DONE:
            return cv_rules.done_result(dets_for_class, old_state)
        else:
            raise Exception('Bad State')
