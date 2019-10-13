import asyncio
import async_timeout
import click
import json
import logging
import paho.mqtt.client
import time
from bleak import discover as bleak_discover
from bleak import BleakClient
from bleak import BleakError

class LifeBaseMeter(object):
    """The BLE device"""
    def __init__(self, mac):
        self.mac = mac
        self.ble = None
        self.is_connected = False
        self.servicefilter = None
        self.characteristicfilter = None
        self.descriptorfilter = None
        self.bleview = False
        self.measurements = []
        self.ble_services = {}

# common name for our devices
LifeBaseMeter.device_name = 'LifeBaseMeter'

#TODO: read those in from a config file or some other central source
#      where the central source overrides the device's setting.
LifeBaseMeter.subject_uuids = {
    "__init__": "54000000-e337-46ca-9690-cdd6d309e7b1",
    "subject_name": "54000001-e337-46ca-9690-cdd6d309e7b1",
    "subject_uuid": "54000002-e337-46ca-9690-cdd6d309e7b1",
    "subject_type_name": "54000003-e337-46ca-9690-cdd6d309e7b1",
    "subject_type_uuid": "54000004-e337-46ca-9690-cdd6d309e7b1"
}

LifeBaseMeter.ignore_services = [
    "00001801-0000-1000-8000-00805f9b34fb"
]

#TODO: read those in from a config file or some other central source
#TODO: and probably move it further down the line towards the frontend
LifeBaseMeter.measuremnt_uuids = {
}

class Service(object):
    """Offline abstraction for a service"""
    def __init__(self, uuid):
        self.uuid = uuid
        self.handle = None
        self.description = ""
        self.characteristics = {}
    def set_handle_from_path(self, path):
        self.handle = path.split('/')[5].replace('service', '0x')

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

class Descriptor(object):
    """Offline abstraction for a descriptor"""
    def __init__(self, uuid):
        self.uuid = uuid
        self.handle = None
        self.description = ""
    def set_handle(self, handle):
        self.handle = hex(handle)

class Config(object):
    """Click CLI configuration"""
    def __init__(self):
        self.macs = []

pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('-d', '--device', 'macs', multiple=True,
    help='The MAC address of the BLE interface to be scanned.')
@click.option('-n', '--device-name', 'device_name',
    default = LifeBaseMeter.device_name,
    help='The common name of LifeBase devices, usually this is "LifeBaseMeter" (default)')
@click.option('-t', '--timeout', 'timeout', default=30, help=
    'Do not wait longer than this amount of seconds for devices to answer')
@pass_config
def main(config, macs, device_name, timeout):
    """Scan BLE devices for LifeBase parameters and send them
        to a MQTT broker."""
    config.macs = macs
    config.device_name = device_name
    config.timeout = timeout

async def run_discovery(device_list, device_name, timeout):
    """Scan for BLE devices but only consider those with a certain name."""
    async with async_timeout.timeout(timeout):
        ds = await bleak_discover()
        for d in ds:
            if d.name == device_name:
                device_list.append(d.address)

def discover_devices(device_list, device_macs, device_name, timeout):
    if device_macs:
        new_list = []
    else:
        new_list = device_list
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_discovery(new_list, device_name,
        timeout))
    for m in device_macs:
        for d in new_list:
            if d == m:
                device_list.append(d)
                break

@main.command()
#@click.option('-w', '--well-known-uuids', 'wellknown',
#  default=wellknown_default, help='The UUID of a LifeBase device',
#  multiple=True)
#@click.option('-W', '--all-devices', 'all', default=False,
#  help='Do not filter by well-known UUIDs')
@pass_config
def discover(config):
    """Scan the air for LifeBaseMeter devices and list them."""
    try:
        device_list = []
        discover_devices(device_list, config.macs, config.device_name,
            config.timeout)
        for d in device_list:
            click.echo(d + " " + config.device_name)
    except asyncio.TimeoutError:
        click.echo("Error: The timeout was reached, you may want to specify it explicitly with --timeout timeout")
    except BleakError:
        click.echo("Error: There was a problem with the BLE connection. Please try again later.")

@main.command()
@click.option('-b/-B', '--ble-view/--no-ble-view', 'bleview',
    default=False, help='Display the results as seen on the BLE device')
@click.option('-s', '--service-filter', 'servicefilter', default=None,
    help='The UUID of a service of interest', multiple=True)
@click.option('-c', '--characteristic-filter', 'characteristicfilter',
    default=None, help='The UUID of a characteristic of interest',
    multiple=True)
@click.option('-d', '--descriptor-filter', 'descriptorfilter', default=None,
    help='The UUID of a descriptor of interest', multiple=True)
@pass_config
def scan(config, bleview, servicefilter, characteristicfilter,
    descriptorfilter):
    """Scan BLE devices for LifeBase parameters."""
    macs = []
    discover_devices(macs, config.macs, config.device_name, config.timeout)
    for m in macs:
        click.echo('Scanning ' + m)
        lifebasemeter = LifeBaseMeter(m)
        lifebasemeter.bleview = bleview
        lifebasemeter.servicefilter = servicefilter
        lifebasemeter.characteristicfilter = characteristicfilter
        lifebasemeter.descriptorfilter = descriptorfilter
        try:
            scan_services(lifebasemeter, config.timeout)
            if lifebasemeter.bleview:
                for s in lifebasemeter.ble_services.values():
                    click.echo("\t{0} ({1}): {2}".format(s.uuid, s.handle,
                            s.description))
                    for ch in s.characteristics.values():
                        click.echo("\t\t{0} ({1}): [{2}]; Name: {3}; Value: {4}".
                            format(ch.uuid, ch.handle, "|".join(ch.properties),
                            ch.description, ch.value))
                        for d in ch.descriptors.values():
                            click.echo("\t\t\t{0} ({1}): Value: {2}".format(
                                d.uuid, d.handle, bytes(d.description)))
            else:
                for measurement in lifebasemeter.measurements:
                    click.echo(format_measurement(measurement))
        except asyncio.TimeoutError:
            click.echo("Error: The timeout was reached, you may want to specify it explicitly with --timeout timeout")
        except BleakError:
            click.echo("Error: There was a problem with the BLE connection. Please try again later.")
        except Exception as e:
            click.echo(e)

def format_measurement(measurement):
    return json.dumps(measurement)

async def run_scan_services_bleview(lifebasemeter, loop, timeout):
    async with async_timeout.timeout(timeout):
        async with BleakClient(lifebasemeter.mac, loop=loop) as client:
            lifebasemeter.ble = await client.get_services()
            for s in lifebasemeter.ble.services.values():
                if lifebasemeter.servicefilter and s.uuid not in lifebasemeter.servicefilter:
                    continue
                service = Service(s.uuid)
                lifebasemeter.ble_services[s.uuid] = service
                service.set_handle_from_path(s.path)
                service.description = s.description
                for ch in s.characteristics:
                    if lifebasemeter.characteristicfilter and ch.uuid not in lifebasemeter.characteristicfilter:
                        continue
                    cc = Characteristic(ch.uuid)
                    service.characteristics[ch.uuid] = cc
                    cc.set_handle_from_path(ch.path)
                    cc.description = ch.description
                    cc.properties = ch.properties
                    if "read" in ch.properties:
                        try:
                            cc.value = bytes(await client.read_gatt_char(ch.uuid))
                        except:
                            cc.value = None
                    for d in ch.descriptors:
                        if lifebasemeter.descriptorfilter and d.uuid not in lifebasemeter.descriptorfilter:
                            continue
                        descriptor = Descriptor(d.uuid)
                        cc.descriptors[d.uuid] = descriptor
                        descriptor.set_handle(d.handle)
                        try:
                            descriptor.description = await client.read_gatt_descriptor(d.handle)
                        except:
                            descriptor.description = None

async def run_scan_services_measurments(lifebasemeter, loop, timeout):
    async with async_timeout.timeout(timeout):
        async with BleakClient(lifebasemeter.mac, loop=loop) as client:
            lifebasemeter.ble = await client.get_services()
            subject = lifebasemeter.ble.services.pop(LifeBaseMeter.subject_uuids["__init__"])
            subject_uuid = None
            subject_name = None
            subject_type_uuid = None
            subject_type_name = None
            for c in subject.characteristics:
                if c.uuid == LifeBaseMeter.subject_uuids["subject_uuid"]:
                    subject_uuid = bytes(await client.read_gatt_char(c.uuid)).decode("utf-8")
                if c.uuid == LifeBaseMeter.subject_uuids["subject_name"]:
                    subject_name = bytes(await client.read_gatt_char(c.uuid)).decode("utf-8")
                if c.uuid == LifeBaseMeter.subject_uuids["subject_type_uuid"]:
                    subject_type_uuid = bytes(await client.read_gatt_char(c.uuid)).decode("utf-8")
                if c.uuid == LifeBaseMeter.subject_uuids["subject_type_name"]:
                    subject_type_name = bytes(await client.read_gatt_char(c.uuid)).decode("utf-8")
            for cuuid in LifeBaseMeter.ignore_services:
                lifebasemeter.ble.services.pop(cuuid)
            for s in lifebasemeter.ble.services.values():
                if lifebasemeter.servicefilter and s.uuid not in lifebasemeter.servicefilter:
                    continue
                for ch in s.characteristics:
                    if lifebasemeter.characteristicfilter and ch.uuid not in lifebasemeter.characteristicfilter:
                        continue
                    measurement = {
                        "uuid": ch.uuid,
                        "subject_uuid": subject_uuid,
                        "subject_name": subject_name,
                        "subject_type_uuid": subject_type_uuid,
                        "subject_type_name": subject_type_name,
                        "service": s.uuid,
                        "timestamp": int(time.time())
                    }
                    lifebasemeter.measurements.append(measurement)
                    if "read" in ch.properties:
                        try:
                            measurement["value"] = float(bytes(await client.read_gatt_char(ch.uuid)))
                        except:
                            measurement["value"] = None

def scan_services(lifebasemeter, timeout):
    loop = asyncio.get_event_loop()
    if lifebasemeter.bleview:
        loop.run_until_complete(run_scan_services_bleview(lifebasemeter, loop, timeout))
    else:
        loop.run_until_complete(run_scan_services_measurments(lifebasemeter, loop, timeout))

@main.command()
##TODO: multiple broker support?
##TODO: certs, credentials, etc.
@click.option('-h', '--hostname', 'brokerhost', default='127.0.0.1',
    help='The MQTT broker hostname to send the data to.')
@click.option('-p', '--port', 'brokerport', default=None,
    help='The MQTT broker port to send the data to.')
@click.option('-s', '--service-filter', 'servicefilter', default=None,
    help='The UUID of a service of interest', multiple=True)
@click.option('-c', '--characteristic-filter', 'characteristicfilter',
    default=None, help='The UUID of a characteristic of interest',
    multiple=True)
@pass_config
def interconnect(config, servicefilter, characteristicfilter, brokerhost, brokerport):
    """Scan the BLE devices and send the data to the MQTT broker."""
    c = paho.mqtt.client.Client("LifeBase-BLE-MQTT")
    macs = []
    discover_devices(macs, config.macs, config.device_name, config.timeout)
    for m in macs:
        click.echo('Scanning ' + m)
        lifebasemeter = LifeBaseMeter(m)
        lifebasemeter.servicefilter = servicefilter
        lifebasemeter.characteristicfilter = characteristicfilter
        try:
            scan_services(lifebasemeter, config.timeout)
        except asyncio.TimeoutError:
            click.echo("Timeout Error for device: " + m)
        except BleakError:
            click.echo("BLE Connection Error: " + m)
        except Exception as e:
            click.echo(e)
        for measurement in lifebasemeter.measurements:
            topics = []
            for a in LifeBaseMeter.device_name, measurement["subject_type_name"], measurement["subject_name"]:
                if a:
                    topics.append(''.join(e for e in a if e.isalnum()))
                else:
                    topics.append('Unknown')
            c.connect(brokerhost)
            c.publish("/".join(topics), format_measurement(measurement))


