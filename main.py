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
        print("Services:", d.ble.services)
        print("Characteristics:", d.ble.characteristics)
    except asyncio.TimeoutError:
        print("Error: The timeout was reached, you may want to specify it explicitly with --timeout timeout")
    except BleakError:
        print("Error: There was a problem with the BLE connection. Please try again later.")
    except Exception as e:
        print(e)

async def run_scan_services(lifebasemeter, loop, timeout):
    async with async_timeout.timeout(timeout):
        async with BleakClient(lifebasemeter.mac, loop=loop) as c:
            lifebasemeter.ble = await c.get_services()

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

