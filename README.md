# LifeBase BLE-MQTT Wrapper

# Development

The entry point of the application is `./main.py`

## Dependencies management, with `pip`

Dependencies are listed both in `./requirements.txt` and in
`./setup.py`.
We install them through `pip`, python's package manager.

## Environement management with `virtualenv`

Source: https://click.palletsprojects.com/en/7.x/quickstart/

We install `virtualenv`. It enables multiple side-by-side
installations of Python and libraries (resp. the versions),
one for each project. It
doesn’t actually install separate copies of Python, but it does
provide a clever way to keep different project environments
isolated.

`sudo pip install virtualenv`

The following command sets the virtual environment up.

`virtualenv venv`

Now, whenever we want to work on a project, we only have to activate the corresponding environment

`. venv/bin/activate`

To stop working on the project:

`deactivate`

NOTE: As this requires python3, on older systems you will want to make
sure to get the correct version installed. You might need, e.g. on debian,
something like `pip3` instead of `pip` and you can provide the correct
version to `virtualenv` with e.g. `--python=python3.5`..

## Modules, `setuptools` integration

> When writing command line utilities, it’s recommended to write them
> as modules that are distributed with setuptools instead of using Unix
> shebangs.
Source: https://click.palletsprojects.com/en/7.x/setuptools/#setuptools-integration

The setup of the application is declared in `./setup.py`.


## Test the script

To test the script we can make a new virtualenv and then install our package:

```
virtualenv venv
. venv/bin/activate
pip install --editable .
```

Afterwards, the command should be available as `lifebase_ble_mqtt`.

(The `pip install --editable` command, is suffixed with a `.`
(dot); it represents the current directory in unix systems. The
`venv/bin/activate`, is prefixed with a `.` (dot); here the dot is
equivalent to `source` and means to read in the commands from
the file specified into the current shell.)

