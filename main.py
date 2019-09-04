import click
import pygatt
import paho.mqtt.client

class Config(object):
    def __init__(self):
        self.macs = []

pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group()
@click.option('-d', '--device', 'macs', help='The MAC address of the BLE interface of the LifeBaseMeter to be scanned.', multiple=True)
@pass_config
def main(config, macs):
    """Scan BLE devices for LifeBase parameters and send them to a MQTT broker."""
    config.macs = macs

@main.command()
@pass_config
def scan(config):
    """Scan BLE devices for LifeBase parameters."""
    for d in config.macs:
        click.echo('Not scanning ' + d + ' yet..')

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
        c.publish("foobar", d)

