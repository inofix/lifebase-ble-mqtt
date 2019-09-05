from setuptools import setup

setup(
    name='lifebase_ble_mqtt',
    version='0.1',
    py_modules=['lifebase_ble_mqtt'],
    install_requires=[
        'Click',
        'paho-mqtt',
        'pexpect',
        'pygatt',
    ],
    entry_points='''
        [console_scripts]
        lifebase_ble_mqtt=main:main
    ''',
)
