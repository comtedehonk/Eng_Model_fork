import supervisor
import storage


# If the switch pin is connected to ground CircuitPython can write to the drive
storage.remount("/", True)

supervisor.runtime.next_stack_limit = 4096 + 4096