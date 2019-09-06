import logging
import asyncio
import time
import argparse
from majortom_gateway import GatewayAPI
from demo.demo_sat import DemoSat

logger = logging.getLogger(__name__)

# Set up command line arguments
parser = argparse.ArgumentParser()
# Required Args
parser.add_argument(
    "majortomhost",
    help='Major Tom host name. Can also be an IP address for local development/on prem deployments.')
parser.add_argument(
    "gatewaytoken",
    help='Gateway Token used to authenticate the connection. Look this up in Major Tom under the gateway page for the gateway you are trying to connect.')

# Optional Args and Flags
parser.add_argument(
    '--systems',
    type=int,
    default=1,
    help='number of systems')
parser.add_argument(
    '--subsystems',
    type=int,
    default=5,
    help='number of subsystems per system (this gateway sends 1 metrics message per subsystem)')
parser.add_argument(
    '--metrics',
    type=int,
    default=50,
    help='number of metrics per subsystem (number of measurements in each metrics message)')
parser.add_argument(
    '--frequency',
    type=int,
    default=1,
    help='frequency of telemetry reporting in Hertz (sends one of each metrics message at this frequency)')
parser.add_argument(
    '-b',
    '--basicauth',
    help='Basic Authentication credentials. Not required unless BasicAuth is active on the Major Tom instance. Must be in the format "username:password".')
parser.add_argument(
    '-l',
    '--loglevel',
    choices=["info", "error"],
    help='Log level for the logger. Defaults to "debug", can be set to "info", or "error".')
parser.add_argument(
    '--http',
    help="If included, you can instruct the gateway to connect without encryption. This is only to support on prem deployments or for local development when not using https.",
    action="store_true")

args = parser.parse_args()

if args.loglevel == 'error':
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
elif args.loglevel == 'info':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger.info("Starting up!")
loop = asyncio.get_event_loop()

logger.debug("Setting up MajorTom")
gateway = GatewayAPI(
    host=args.majortomhost,
    gateway_token=args.gatewaytoken,
    basic_auth=args.basicauth,
    command_callback=demo_sat.command_callback,
    cancel_callback=demo_sat.cancel_callback,
    http=args.http)

logger.debug("Connecting to MajorTom")
asyncio.ensure_future(gateway.connect_with_retries())

logger.debug("Starting Event Loop")
loop.run_forever()
