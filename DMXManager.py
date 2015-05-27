import array

from libs.loop import Loop
from libs.pygame_midi_input import MidiInput

from ArtNet3 import ArtNet3

import logging
log = logging.getLogger(__name__)

VERSION = '0.03'

DEFAULT_FRAMERATE = 30
DEFAULT_MIDI_PORT_NAME = 'nanoKONTROL2'


class AbstractDMXRenderer(object):
    DEFAULT_DMX_SIZE = 128

    def __init__(self, dmx_size=DEFAULT_DMX_SIZE):
        self.dmx_universe = array.array('B')
        self.dmx_universe.frombytes(b'\xff'*dmx_size)

    def render(self, frame):
        """
        Given a frame number (that can be ignored)
        Return a dmx_universe byte array
        """
        raise Exception('should override')
        return self.dmx_universe

    def close(self):
        raise Exception('should override')


class DMXManager(AbstractDMXRenderer):

    def __init__(self, renderers, framerate=DEFAULT_FRAMERATE):
        super().__init__()

        assert len(renderers), "Must provide renderers"
        self.renderers = renderers

        self.artnet = ArtNet3()

        self.loop = Loop(framerate)
        self.loop.render = self.render
        self.loop.close = self.close

        self.loop.run()

    def close(self):
        for renderer in self.renderers:
            renderer.close()

    def render(self, frame):
        for index, values in enumerate(zip(*(renderer.render(frame) for renderer in self.renderers))):
            # Perform mixing of this dmx byte across the renderers
            self.dmx_universe[index] = max(values)
        self.artnet.dmx(self.dmx_universe.tobytes())


class DMXRendererMidiInput(AbstractDMXRenderer):
    CONTROL_OFFSET_JUMP = 8

    def __init__(self, name):
        super().__init__()

        self.midi_input = MidiInput(name)
        self.midi_input.init_pygame()
        self.midi_input.midi_event = self.midi_event  # Dynamic POWER!!!! Remap the midi event to be on this object!

        self._control_offset = 0

    def render(self, frame):
        self.midi_input.process_events()
        return self.dmx_universe

    def midi_event(self, event, data1, data2, data3):
        if data1 == 46:
            self.loop.running = False
        if data1 == 59 and data2 == 127:
            self.control_offset += self.CONTROL_OFFSET_JUMP
            log.info('control_offset: {0}'.format(self.control_offset))
        if data1 == 58 and data2 == 127:
            self.control_offset += -self.CONTROL_OFFSET_JUMP
            log.info('control_offset: {0}'.format(self.control_offset))
        if data1 >= 0 and data1 < self.CONTROL_OFFSET_JUMP:
            self.dmx_universe[self.control_offset + data1] = data2 * 2
        #print('lights2 {0} {1} {2} {3}'.format(event, data1, data2, data3))

    def close(self):
        self.midi_input.close()

    @property
    def control_offset(self):
        return self._control_offset
    @control_offset.setter
    def control_offset(self, value):
        self._control_offset = min((max(0, int(value))), min(512, len(self.dmx_universe) - self.CONTROL_OFFSET_JUMP))


def get_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description="""DMXManager - Lighting Automation Framework

        """,
        epilog="""
        """
    )
    parser_input = parser

    parser.add_argument('-f', '--framerate', action='store', help='Frames per second to send ArtNet3 packets', default=DEFAULT_FRAMERATE)
    parser.add_argument('--midi_input', action='store', help='name of the midi input port to use', default=DEFAULT_MIDI_PORT_NAME)

    parser.add_argument('--log_level', type=int,  help='log level', default=logging.INFO)
    parser.add_argument('--version', action='version', version=VERSION)

    args = parser.parse_args()

    return vars(args)


if __name__ == "__main__":
    args = get_args()
    logging.basicConfig(level=args['log_level'])

    DMXManager(
        renderers = (
            DMXRendererMidiInput(args['midi_input']),
        ),
        framerate = args['framerate'],
    )