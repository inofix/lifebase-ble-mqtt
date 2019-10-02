import click
import logging
import asyncio
import async_timeout
from bleak import discover as bleak_discover
from bleak import BleakClient
from bleak import BleakError
import paho.mqtt.client

device_name_default = 'LifeBaseMeter'
#TODO also check for known uuids?
#wellknown_default = [ 'e9979b5f-c2c7-45f6-8377-7c94e0b1a7e4' ]

# store all available BLE devices (LifeBaseMeter objects) in here
lifebase_devices = []

class LifeBaseMeter(object):
    """The BLE device"""
    def __init__(self, mac):
        self.mac = mac
        self.ble = None
        self.is_connected = False
        self.measurements = {}

class Service(object):
    """Offline abstraction for a service"""
    def __init__(self, uuid):
        self.uuid = uuid
        self.handle = None
        self.description = ""
        self.characteristics = {}
    def set_handle_from_path(self, path):
        self.handle = path.split('/')[5].replace('service', '0x')
    def get_handle(self, as_hex=True):
        """Return the BLE handle either in 'hex' or 'dec'"""
        if as_hex:
            return self.handle
        else:
            return int(h, 16)
    def add_characteristic(self, characteristic):
        self.characteristics[characteristic.uuid] = characteristic

class Characteristic(object):
    """Offline abstraction for a characteristic
        aka measurement, in this context"""
    def __init__(self, uuid):
        self.uuid = uuid
        self.handle = None
        self.value = None
        self.properties = []
        self.description = None
        self.descriptors = {}
    def set_handle_from_path(self, path):
        self.handle = path.split('/')[6].replace('char', '0x')
    def get_handle(self, as_hex=True):
        """Return the BLE handle either in 'hex' or 'dec'"""
        if as_hex:
            return self.handle
        else:
            return int(h, 16)
    def add_descriptor(self, descriptor):
        self.descriptors[descriptor.uuid] = descriptor

class Descriptor(object):
    """Offline abstraction for a descriptor"""
    def __init__(self, uuid):
        self.uuid = uuid
        self.handle = None
        self.description = ""
    def set_handle(self, handle):
        self.handle = hex(handle)
    def get_handle(self, as_hex=True):
        """Return the BLE handle either in 'hex' or 'dec'"""
        if as_hex:
            return self.handle
        else:
            return int(self.handle, 16)

class Config(object):
    """Click CLI configuration"""
    def __init__(self):
        self.macs = []

pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('-d', '--device', 'macs', help='The MAC address of the BLE interface to be scanned.', multiple=True)
@click.option('-t', '--timeout', 'timeout', default=30, help='Do not wait longer than this amount of seconds for devices to answer')
#@click.option('-c', '--characteristic', 'characteristic', help='The characteristic of interest to be read.', multiple=True)
@pass_config
def main(config, macs, timeout):
    """Scan BLE devices for LifeBase parameters and send them to a MQTT broker."""
    config.macs = macs
    config.timeout = timeout

async def run_discovery(lifebase_devices, device_name, timeout):
    """Scan for BLE devices but only consider those with a certain name."""
    async with async_timeout.timeout(timeout):
        ds = await bleak_discover()
        for d in ds:
            if d.name == device_name:
                lifebase_devices.append(d)

@main.command()
@click.option('-n', '--device-name', 'device_name', default=device_name_default, help='The common name of LifeBaseMeter devices')
#@click.option('-w', '--well-known-uuids', 'wellknown', default=wellknown_default, help='The UUIDs of known LifeBase devices', multiple=True)
#@click.option('-W', '--all-devices', 'all', default=False, help='Do not filter by well-known UUIDs')
@pass_config
def discover(config, device_name):
    """Scan the air for LifeBaseMeter devices and list them."""
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_discovery(lifebase_devices, device_name, config.timeout))
        for d in lifebase_devices:
            print(d)
    except asyncio.TimeoutError:
        print("Error: The timeout was reached, you may want to specify it explicitly with --timeout timeout")
    except BleakError:
        print("Error: There was a problem with the BLE connection. Please try again later.")

@main.command()
@pass_config
def scan(config):
    """Scan BLE devices for LifeBase parameters."""
    for m in config.macs:
        click.echo('Scanning ' + m)
        d = LifeBaseMeter(m)
    try:
        scan_services(d, config.timeout)
        for s in d.measurements.values():
            print("\t{0} ({1}): {2}".format(s.uuid, s.handle, s.description))
            for ch in s.characteristics.values():
                print("\t\t{0} ({1}): [{2}]; Name: {3}; Value: {4}".format(
                    ch.uuid, ch.handle, "|".join(ch.properties), ch.description, ch.value))
                for de in ch.descriptors.values():
                    print("\t\t\t{0} ({1}): Value: {2}".format(
                        de.uuid, de.handle, bytes(de.description)))
    except asyncio.TimeoutError:
        print("Error: The timeout was reached, you may want to specify it explicitly with --timeout timeout")
    except BleakError:
        print("Error: There was a problem with the BLE connection. Please try again later.")
    except Exception as e:
        print(e)

async def run_scan_services(lifebasemeter, loop, timeout):
#TODO add filters to skip elements on request..
    async with async_timeout.timeout(timeout):
        async with BleakClient(lifebasemeter.mac, loop=loop) as c:
            lifebasemeter.ble = await c.get_services()
            lifebasemeter.is_connected = await c.is_connected()
            for s in c.services:
                service = Service(s.uuid)
                lifebasemeter.measurements[s.uuid] = service
                service.set_handle_from_path(s.path)
                service.description = s.description
                for ch in s.characteristics:
                    characteristic = Characteristic(ch.uuid)
                    service.characteristics[ch.uuid] = characteristic
                    characteristic.set_handle_from_path(ch.path)
                    characteristic.description = ch.description
                    characteristic.properties = ch.properties
                    if "read" in ch.properties:
                        try:
                            characteristic.value = bytes(await c.read_gatt_char(ch.uuid))
                        except:
                            characteristic.value = None
                    for d in ch.descriptors:
                        descriptor = Descriptor(d.uuid)
                        characteristic.descriptors[d.uuid] = descriptor
                        descriptor.set_handle(d.handle)
                        try:
                            descriptor.description = await c.read_gatt_descriptor(d.handle)
                        except:
                            descriptor.description = None

def scan_services(lifebasemeter, timeout):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_scan_services(lifebasemeter, loop, timeout))

@main.command()
##TODO: multiple broker support?
##TODO: certs, credentials, etc.
@click.option('-h', '--hostname', 'brokerhost', default=None, help='The MQTT broker hostname to send the data to.')
@click.option('-p', '--port', 'brokerport', default=None, help='The MQTT broker port to send the data to.')
@pass_config
def transport(config, brokerhost, brokerport):
    """Scan the BLE devices and send the data to the MQTT broker."""
    c = paho.mqtt.client.Client("LifeBase-BLE-MQTT")
    c.connect(brokerhost)
    for d in config.macs:
        c.publish("LifeBaseMeter", d)

