from enum import Enum
import ikea_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine


ONE_WIRE_INSTRUCTION_BYTES = ('You have inserted one wire. Now insert the '
                              'second wire to support the shade.'.encode())


class State(Enum):
    BASE = ('Put the base on the table.', 'base.PNG',
            ikea_pb2.State.Step.BASE)
    PIPE = ('Screw the pipe on top of the base.', 'pipe.PNG',
            ikea_pb2.State.Step.PIPE)
    SHADE = ('Good job. Now find the shade cover and expand it.', 'shade.PNG',
             ikea_pb2.State.Step.SHADE)
    BUCKLE = ('Insert the iron wires to support the shade. Then show the top '
              'view of the shade', 'buckle.PNG', ikea_pb2.State.Step.BUCKLE)
    BLACKCIRCLE = ('Great. Now unscrew the black ring out of the pipe, and put '
                   'it on the table.', 'blackcircle.PNG',
                   ikea_pb2.State.Step.BLACKCIRCLE)
    LAMP = ('Now put the shade on top of the base, and screw the black ring'
            ' back.', 'lamp.PNG', ikea_pb2.State.Step.LAMP)
    BULB = ('Find the bulb and put it on the table.', 'bulb.PNG',
            ikea_pb2.State.Step.BULB)
    BULBTOP = ('Good. Last step. Screw in the bulb and show me the top view.',
               'lamptop.PNG', ikea_pb2.State.Step.BULBTOP)
    DONE = ('Congratulations. You have finished assembling the lamp.',
            'lamp.PNG', ikea_pb2.State.Step.DONE)

    def __init__(self, speech, image_filename, proto_step):
        self._speech_bytes = speech.encode()
        image_path = os.path.join(IMAGE_DIR, image_filename)
        self._image_bytes = open(image_path, 'rb').read()
        self._proto_step = proto_step

    def get_proto_step(self):
        return self._proto_step

    def create_result_wrapper(self, update_count):
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT
        result.payload = self._speech_bytes
        result_wrapper.results.append(result)

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.IMAGE
        result.payload = self._image_bytes
        result_wrapper.results.append(result)

        logger.info('Updated State: %s', self.name)

        to_client_extras = ikea_pb2.ToClientExtras()
        to_client_extras.state.update_count = update_count
        to_client_extras.state.step = self.get_proto_step()

        result_wrapper.extras.Pack(to_client_extras)

        return result_wrapper


# Class indexes come from the following code:
# LABELS = ["base", "pipe", "shade", "shadetop", "buckle", "blackcircle",
#           "lamp", "bulb", "bulbtop"]
# with open(os.path.join('model', 'labels.txt')) as f:
#     idx = 1
#     for line in f:
#         line = line.strip()
#         print(line.upper(), '=', idx)
#         idx += 1
SHADETOP = 1
BULBTOP = 2
BUCKLE = 3
LAMP = 4
PIPE = 5
BLACKCIRCLE = 6
BASE = 7
SHADE = 8
BULB = 9


def _result_without_update(state):
    status = gabriel_pb2.ResultWrapper.Status.SUCCESS
    result_wrapper = cognitive_engine.create_result_wrapper(status)

    to_client_extras = ikea_pb2.ToClientExtras()
    to_client_extras.state = state  # TODO take step instead of state

    result_wrapper.extras.Pack(to_client_extras)
    return result_wrapper


def base_result(dets_for_class, old_state):
    if len(dets_for_class[BASE]) == 0:
        return _result_without_update(old_state)

    update_count = old_state.update_count + 1
    return State.PIPE.create_result_wrapper(update_count)


def pipe_result(dets_for_class, old_state):
    bases = dets_for_class[BASE]
    pipes = dets_for_class[PIPE]
    if (len(bases) == 0) or (len(pipes) == 0):
        return _result_without_update(old_state)

    for base in bases:
        base_center = ((base[0] + base[2]) / 2, (base[1] + base[3]) / 2)
        base_width = base[2] - base[0]
        base_height = base[3] - base[1]
        for pipe in pipes:
            pipe_center = ((pipe[0] + pipe[2]) / 2, (pipe[1] + pipe[3]) / 2)
            pipe_height = pipe[3] - pipe[1]
            if pipe_center[1] > base_center[1]:
                continue
            if pipe_center[0] < base_center[0] - base_width * 0.25 or (
                    pipe_center[0] > base_center[0] + base_width * 0.25):
                continue
            if pipe_height / base_height < 1.5:
                continue

            update_count = old_state.update_count + 1
            return State.SHADE.create_result_wrapper(update_count)

    return _result_without_update(old_state)


def shade_result(dets_for_class, old_state):
    if len(dets_for_class[SHADE]) > 0:
        update_count = old_state.update_count + 1
        return State.BUCKLE.create_result_wrapper(update_count)

    return _result_without_update(old_state)


def _count_buckles(shadetops, buckles):
    for shadetop in shadetops:
        shadetop_center = ((shadetop[0] + shadetop[2]) / 2,
                           (shadetop[1] + shadetop[3]) / 2)
        shadetop_width = shadetop[2] - shadetop[0]
        shadetop_height = shadetop[3] - shadetop[1]

        left_buckle = False
        right_buckle = False
        for buckle in buckles:
            buckle_center = ((buckle[0] + buckle[2]) / 2,
                             (buckle[1] + buckle[3]) / 2)
            if buckle_center[1] < shadetop[1] or buckle_center[1] > shadetop[3]:
                continue
            if buckle_center[0] < shadetop[0] or buckle_center[0] > shadetop[2]:
                continue
            if buckle_center[0] < shadetop_center[0]:
                left_buckle = True
            else:
                right_buckle = True
        if left_buckle and right_buckle:
            break

    return int(left_buckle) + int(right_buckle)


def _buckle_result(dets_for_class, old_state):
    status = gabriel_pb2.ResultWrapper.Status.SUCCESS
    result_wrapper = cognitive_engine.create_result_wrapper(status)
    frames_with_one_buckle = old_state.frames_with_one_buckle
    frames_with_two_buckles = old_state.frames_with_two_buckles
    update_count = old_state.update_count

    shadetops = dets_for_class[SHADETOP]
    buckles = dets_for_class[BUCKLE]
    if (len(shadetops) == 0) or (len(buckles) == 0):
        return _result_without_update(old_state)

    n_buckles = _count_buckles(shadetops, buckles)
    if n_buckles == 2:
        frames_with_one_buckle = 0
        frames_with_two_buckles += 1
        update_count += 1

        if frames_with_two_buckles > 3:
            return State.LAMP.create_result_wrapper(update_count)
    elif n_buckles == 1:
        frames_with_one_buckle += 1
        frames_with_two_buckles = 0
        update_count += 1

        # We only give this instruction when frames_with_one_buckle is
        # exactly 5 so it does not get repeated
        if engine_fields.ikea.frames_with_one_buckle == 5:
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = ONE_WIRE_INSTRUCTION_BYTES
            result_wrapper.results.append(result)

            logger.info('sending second wire message')

    to_client_extras = ikea_pb2.ToClientExtras()
    to_client_extras.state.update_count = update_count
    to_client_extras.state.step = State.BUCKLE.get_proto_step()
    to_client_extras.state.frames_with_one_buckle = frames_with_one_buckle
    to_client_extras.state.frames_with_two_buckles = frames_with_two_buckles

    result_wrapper.extras.Pack(to_client_extras)
    return result_wrapper
