from multiprocessing import Process, Pipe
import http_server

import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
from enum import Enum
import sandwich_pb2
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


PROTOTXT = 'model/faster_rcnn_test.pt'
CAFFEMODEL = 'model/model.caffemodel'

# Max image width and height
IMAGE_MAX_WH = 640

CONF_THRESH = 0.5
NMS_THRESH = 0.3

IMAGE_DIR = 'images'

# The following code outputs [7, 4, 8, 1, 3, 2, 5, 6, 0]:
# # build a mapping between faster-rcnn recognized object order to a
# # standard order
# LABELS = ["bread", "ham", "cucumber", "lettuce", "cheese", "half", "hamwrong",
#           "tomato", "full"]
# self._object_mapping = [-1] * len(LABELS)
# with open(os.path.join('model', 'labels.txt')) as f:
#     lines = f.readlines()
#     for idx, line in enumerate(lines):
#         line = line.strip()
#         self._object_mapping[idx] = LABELS.index(line)
# print(self._object_mapping)
BREAD = 8
HAM = 3
LETTUCE = 4
HALF = 6
TOMATO = 0
FULL = 2


if not os.path.isfile(CAFFEMODEL):
    raise IOError(('{:s} not found.').format(CAFFEMODEL))


faster_rcnn_config.TEST.HAS_RPN = True  # Use RPN for proposals

logger = logging.getLogger(__name__)


class State(Enum):
    NOTHING = ('This text should never be sent to the client.', 'bread.jpg')
    BREAD = ('Now put a piece of bread on the table.', 'bread.jpg')
    HAM = ('Now put a piece of ham on the bread.', 'ham.jpg')
    LETTUCE = ('Now put a piece of lettuce on the ham.', 'lettuce.jpg')
    HALF = ('Now put a piece of bread on the lettuce.', 'half.jpg')
    TOMATO = ('Now put a piece of tomato on the bread.', 'tomato.jpg')
    FULL = ('Now put the bread on top.', 'full.jpg')
    DONE = ('You are done!', 'full.jpg')

    def __init__(self, speech, image_filename):
        self._speech = speech
        image_path = os.path.join(IMAGE_DIR, image_filename)
        self._image_bytes = open(image_path, 'rb').read()

    def get_speech(self):
        return self._speech

    def get_image_bytes(self):
        return self._image_bytes

class SandwichEngine(cognitive_engine.Engine):
    def __init__(self):
        http_server_conn, self._engine_conn = Pipe()
        self._http_server_process = Process(
            target=http_server.start_http_server,
            args=(http_server_conn,))
        self._http_server_process.start()

        self._state = State.NOTHING

        caffe.set_mode_gpu()

        # 0 is the default GPU ID
        caffe.set_device(0)
        faster_rcnn_config.GPU_ID = 0

        self.net = caffe.Net(PROTOTXT, CAFFEMODEL, caffe.TEST)
        # Warmup on a dummy image
        img = 128 * np.ones((300, 500, 3), dtype=np.uint8)
        for i in range(2):
            _, _ = im_detect(self.net, img)
        logger.info('Caffe net has been initilized')

    def _contains_one_object(self, img, cls_idx):
        scores, boxes = im_detect(self.net, img)

        cls_idx += 1 # because we skipped background
        cls_boxes = boxes[:, 4 * cls_idx : 4 * (cls_idx + 1)]
        cls_scores = scores[:, cls_idx]

        # dets: detected results, each line is in
        #       [x1, y1, x2, y2, confidence] format
        dets = np.hstack((cls_boxes, cls_scores[:, np.newaxis])).astype(
            np.float32)

        # non maximum suppression
        keep = nms(dets, NMS_THRESH)
        dets = dets[keep, :]

        # filter out low confidence scores
        inds = np.where(dets[:, -1] >= CONF_THRESH)[0]
        return len(inds) == 1

    def handle(self, input_frame):
        if self._state == State.DONE:
            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            return cognitive_engine.create_result_wrapper(status)

        to_server = cognitive_engine.unpack_extras(sandwich_pb2.ToServer,
                                                   input_frame)

        if to_server.zoom_status == sandwich_pb2.ToServer.ZoomStatus.START:
            msg = {
                'zoom_action': 'start',
                'state': self._state.name.lower()
            }
            self._engine_conn.send(msg)
            logger.info('Zoom Started')

            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)

            to_client = sandwich_pb2.ToClient()
            to_client.app_key = credentials.ANDROID_KEY
            to_client.app_secret = credentials.ANDROID_SECRET
            to_client.meeting_number = credentials.MEETING_NUMBER
            to_client.meeting_password = credentials.MEETING_PASSWORD

            result_wrapper.extras.Pack(to_client)
            return result_wrapper
        elif to_server.zoom_status == sandwich_pb2.ToServer.ZoomStatus.STOP:
            msg = {
                'zoom_action': 'stop'
            }
            self._engine_conn.send(msg)
            pipe_output = self._engine_conn.recv()
            new_state = pipe_output.get('state')
            self._state = State[new_state.upper()]
            logger.info('Zoom Stopped. New state: %s', new_state)
            return self._result_wrapper_for_state()

        assert len(input_frame.payloads) == 1
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            return cognitive_engine.create_result_wrapper(status)

        width = to_server.width
        height = to_server.height
        if width > IMAGE_MAX_WH or height > IMAGE_MAX_WH:
            raise Exception('Image too large')

        yuv = np.frombuffer(input_frame.payloads[0], dtype=np.uint8)
        yuv = np.reshape(yuv, ((height + (height//2)), width))
        img = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_NV21)
        img = np.rot90(img, 3)

        new_state = self._determine_state(img)

        if new_state == self._state:
            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            return result_wrapper

        self._state = new_state
        return self._result_wrapper_for_state()

    def _result_wrapper_for_state(self):
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT
        result.payload = self._state.get_speech().encode()
        result_wrapper.results.append(result)

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.IMAGE
        result.payload = self._state.get_image_bytes()
        result_wrapper.results.append(result)

        logger.info('sending %s', self._state.get_speech())

        return result_wrapper

    def _determine_state(self, img):
        if self._state == State.NOTHING:
            return State.BREAD
        elif self._state == State.BREAD:
            if self._contains_one_object(img, BREAD):
                return State.HAM
        elif self._state == State.HAM:
            if self._contains_one_object(img, HAM):
                return State.LETTUCE
        elif self._state == State.LETTUCE:
            if self._contains_one_object(img, LETTUCE):
                return State.HALF
        elif self._state == State.HALF:
            if self._contains_one_object(img, HALF):
                return State.TOMATO
        elif self._state == State.TOMATO:
            if self._contains_one_object(img, TOMATO):
                return State.FULL
        elif self._state == State.FULL:
            if self._contains_one_object(img, FULL):
                return State.DONE
        else:
            print('This should raise exception')
            raise Exception('Bad State')

        return self._state
