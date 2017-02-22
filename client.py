import argparse

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(title="Commands")

device_list_parser = subparsers.add_parser("devices")
device_list_parser.set_defaults()

device_parser = subparsers.add_parser("device")
device_parser.add_argument("--device", "-d", nargs=1, metavar="DEVICE", required=True)
device_parser.add_argument("--model", "-m", action="store_true", default=False, help="")
device_parser.add_argument("--id", "-i", action="store_true", default=True, help="")
device_parser.add_argument("--token", "-t", action="store_true", default=False, help="")
device_parser.add_argument("command", nargs=1, choices=["alias", "remove"])
device_parser.add_argument("params", nargs="*")

notify_parser = subparsers.add_parser("notify")

auth_parser = subparsers.add_parser("auth")
