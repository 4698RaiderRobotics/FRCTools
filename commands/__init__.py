# Here you define the commands that will be added to your add-in.

# If you want to add an additional command, duplicate one of the existing directories and import it here.
# You need to use aliases (import "entry" as "my_module") assuming you have the default module named "entry".
from .CCDistance import entry as CCDistance
from .BoltPattern import entry as BoltPattern
from .TimingBelt import entry as TimingBelt
from .TimingPulley import entry as TimingPulley
from .Tubify import entry as Tubify

# Fusion will automatically call the start() and stop() functions.
commands = [
    CCDistance,
    BoltPattern,
    TimingBelt,
    TimingPulley,
    Tubify
]


# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start():
    for command in commands:
        command.start()


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()