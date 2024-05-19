import supervisor
import storage
storage.remount("/", True)
supervisor.runtime.next_stack_limit = 4096 + 4096