import time
from debugcolor import co
import traceback

class cdh:
    # OTA command lookup & dispatch
    def debug_print(self,statement):
            if self.debug:
                print(co("[cdh]" + statement, 'orange', 'bold'))
    def __init__(self,cubesat,debug):
        self.debug=debug
        self.cubesat=cubesat
        # our 4 byte code to authorize commands
        # pass-code for DEMO PURPOSES ONLY
        self.super_secret_code = b'\x59\x4e\x45\x3f'
        self.debug_print(f"Super secret code is: {self.super_secret_code}")
        self.commands = {
            b'\x8eb':    'noop',
            b'\xd4\x9f': 'hreset',   # new
            b'\x12\x06': 'shutdown',
            b'8\x93':    'query',    # new
            b'\x96\xa2': 'exec_cmd',
        }
    ############### hot start helper ###############
    def hotstart_handler(self,msg):
        # try
        try:
            self.cubesat.radio1.node = self.cubesat.cfg['id'] # this sat's radiohead ID
            self.cubesat.radio1.destination = self.cubesat.cfg['gs'] # target gs radiohead ID
        except: pass
        # check that message is for me
        if msg[0]==self.cubesat.radio1.node:
            # TODO check for optional radio config

            # manually send ACK
            self.cubesat.radio1.send('!',identifier=msg[2],flags=0x80)
            # TODO remove this delay. for testing only!
            time.sleep(0.5)
            self.message_handler(msg)
        else:
            print(f'not for me? target id: {hex(msg[0])}, my id: {hex(self.cubesat.radio1.node)}')

    ############### message handler ###############
    def message_handler(self,msg):
        multi_msg=False
        if len(msg) >= 10: # [RH header 4 bytes] [pass-code(4 bytes)] [cmd 2 bytes]
            if bytes(msg[4:8])==self.super_secret_code:
                # check if multi-message flag is set
                if msg[3] & 0x08:
                    multi_msg=True
                # strip off RH header
                msg=bytes(msg[4:])
                cmd=msg[4:6] # [pass-code(4 bytes)] [cmd 2 bytes] [args]
                cmd_args=None
                if len(msg) > 6:
                    print('command with args')
                    try:
                        cmd_args=msg[6:] # arguments are everything after
                        print('cmd args: {}'.format(cmd_args))
                    except Exception as e:
                        print('arg decoding error: {}'.format(e))
                if cmd in self.commands:
                    try:
                        if cmd_args is None:
                            print('running {} (no args)'.format(self.commands[cmd]))
                            # eval a string turns it into a func name
                            eval(self.commands[cmd])(self.cubesat)
                        else:
                            print('running {} (with args: {})'.format(self.commands[cmd],cmd_args))
                            eval(self.commands[cmd])(self.cubesat,cmd_args)
                    except Exception as e:
                        print('something went wrong: {}'.format(e))
                        self.cubesat.radio1.send(str(e).encode())
                else:
                    print('invalid command!')
                    self.cubesat.radio1.send(b'invalid cmd'+msg[4:])
                # check for multi-message mode
                if multi_msg:
                    # TODO check for optional radio config
                    print('multi-message mode enabled')
                    response = self.cubesat.radio1.receive(keep_listening=True,with_ack=True,with_header=True,view=True,timeout=10)
                    if response is not None:
                        self.cubesat.c_gs_resp+=1
                        self.message_handler(response)
            else:
                print('bad code?')


    ########### commands without arguments ###########
    def noop(self):
        print('no-op')
        pass

    def hreset(self):
        print('Resetting')
        try:
            self.cubesat.radio1.send(data=b'resetting')
            self.cubesat.micro.on_next_reset(self.self.cubesat.micro.RunMode.NORMAL)
            self.cubesat.micro.reset()
        except:
            pass

    ########### commands with arguments ###########

    def shutdown(self,args):
        # make shutdown require yet another pass-code
        if args == b'\x0b\xfdI\xec':
            print('valid shutdown command received')
            # set shutdown NVM bit flag
            self.cubesat.f_shtdwn=True
            # stop all tasks
            for t in self.cubesat.scheduled_tasks:
                self.cubesat.scheduled_tasks[t].stop()
            self.cubesat.powermode('minimum')

            """
            Exercise for the user:
                Implement a means of waking up from shutdown
                See beep-sat guide for more details
                https://pycubed.org/resources
            """

            # deep sleep + listen
            # TODO config radio
            self.cubesat.radio1.listen()
            if 'st' in self.cubesat.cfg:
                _t = self.cubesat.cfg['st']
            else:
                _t=5
            import alarm, board
            pin_alarm = alarm.pin.PinAlarm(pin=board.DAC0,value=True)
            time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + eval('1e'+str(_t))) # default 1 day
            # set hot start flag right before sleeping
            self.cubesat.f_hotstrt=True
            alarm.exit_and_deep_sleep_until_alarms(pin_alarm,time_alarm)


    def query(self,args):
        print(f'query: {args}')
        print(self.cubesat.radio1.send(data=str(eval(args))))

    def exec_cmd(self,args):
        print(f'exec: {args}')
        exec(args)