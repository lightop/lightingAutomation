from libs.loop import Loop

from libs.misc import run_funcs, postmortem
from libs.client_reconnect import SubscriptionClient

from lighting import AbstractDMXRenderer, mix, LightingConfig, add_default_argparse_args
from lighting.ArtNet3 import ArtNet3
from lighting.renderers.LightTiming import LightTiming
from lighting.renderers.DisplayTriggerEvents import DisplayTriggerEvents
from lighting.renderers.RemoteControl import RemoteControl
#from lighting.renderers.Ambilight import AmbilightPlayer


import logging
log = logging.getLogger(__name__)

VERSION = '0.05'

DEFAULT_DISPLAYTRIGGER_HOST = '127.0.0.1'
DEFAULT_ARTNET_DMX_HOST = '127.0.0.1'
DEFAULT_FRAMERATE = 30
DEFAULT_YAML_SCAN_INTERVAL = 1.0

class DMXManager(AbstractDMXRenderer):

    def __init__(self, renderers, **kwargs):
        """
        """
        super().__init__()

        assert len(renderers), "Must provide renderers"
        self.renderers = renderers

        self.artnet = ArtNet3(host=kwargs['artnet_dmx_host'])

        if kwargs.get('displaytrigger_host'):
            self.net = SubscriptionClient(host=kwargs['displaytrigger_host'], subscriptions=('lights', 'all'))
            self.net.recive_message = self.recive_message

        self.loop = Loop(kwargs['framerate'])
        self.loop.render = self.render
        self.loop.close = self.close

        self.loop.run()

    def close(self):
        for renderer in self.renderers:
            renderer.close()

    def render(self, frame):
        """
        Frame Event
        Render all registered renderers
        Mix all rendered bytestreams into a single bytestream
        Send DMX display command over network
        """
        mix(self.dmx_universe, tuple(renderer.render(frame) for renderer in self.renderers))
        self.artnet.dmx(self.dmx_universe.tobytes())

    def recive_message(self, message):
        """
        Network Event
        Trigger the correct network event to the correct renderer
        """
        run_funcs(message, self.renderers)


def get_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description="""lightingAutomation - Lighting Automation Framework
        Simple lighting automation for a single DMX universe driven by YAML scene and sequence descriptions.
        Can be remotely controled by trigger events, midi remote or web remote
        """,
        epilog="""
        """
    )
    parser_input = parser

    # Core
    parser.add_argument('--displaytrigger_host', action='store', help='display-trigger server to recieve events from', default=DEFAULT_DISPLAYTRIGGER_HOST)
    parser.add_argument('-f', '--framerate', action='store', help='Frames per second to send ArtNet3 packets', type=int, default=DEFAULT_FRAMERATE)
    parser.add_argument('--artnet_dmx_host', action='store', help='ArtNet3 ip address', default=DEFAULT_ARTNET_DMX_HOST)

    # Plugin params
    parser.add_argument('--yamlscaninterval', action='store', type=float, help='seconds to scan', default=DEFAULT_YAML_SCAN_INTERVAL)

    add_default_argparse_args(parser, version=VERSION)

    args = parser.parse_args()
    return vars(args)


def main(**kwargs):
    config = LightingConfig(kwargs['yamlpath'])

    renderers = []
    light_renderer = LightTiming(config, kwargs['yamlpath'], rescan_interval=kwargs['yamlscaninterval'])
    remote_control_renderer = RemoteControl(config)
    renderers.append(light_renderer)
    renderers.append(remote_control_renderer)
    renderers.append(DisplayTriggerEvents((light_renderer, remote_control_renderer)))

    try:
        from lighting.renderers.PentatonicHero import DMXRendererPentatonicHero
        renderers.append(DMXRendererPentatonicHero())
        log.info('Init: PentatonicHero')
    except ImportError:
        pass

    DMXManager(renderers, **kwargs)


if __name__ == "__main__":
    kwargs = get_args()
    logging.basicConfig(level=kwargs['log_level'])

    def launch():
        main(**kwargs)
    if kwargs.get('postmortem'):
        postmortem(launch)
    else:
        launch()
