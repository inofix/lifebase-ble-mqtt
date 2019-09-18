from setuptools import setup

setup(
    name='lifebase_ble_mqtt',
    version='0.1',
    py_modules=['lifebase_ble_mqtt'],
    install_requires=[
        'asyncio',
        'async_timeout',
        'bleak',
        'Click',
        'paho-mqtt',
        'service_identity',
    ],
    entry_points='''
        [console_scripts]
        lifebase_ble_mqtt=main:main
    ''',
)
