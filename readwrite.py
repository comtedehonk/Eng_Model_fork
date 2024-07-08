with open("boot.py", "w") as f:
    f.write("import storage\nimport supervisor\nstorage.remount('/', True)\nsupervisor.set_next_stack_limit(4096 + 4096)")