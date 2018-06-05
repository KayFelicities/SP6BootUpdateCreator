"""
sp6 merge
"""
import os
import sys
import getopt
import configparser
import traceback
import time
import hashcalc

VERSION = 'V0.1'
DATE = '20180601'

WORKING_PATH = None
SOFTWARE_PATH = os.path.join(os.path.split(os.path.abspath(sys.argv[0]))[0])
SOFTWARE_REAL_PATH = sys._MEIPASS if getattr(sys, 'frozen', False) else SOFTWARE_PATH
CONFIG_FILE = os.path.join(SOFTWARE_PATH, r'bootupdate.ini')
CONFIG_FILE_CONTENT_DEFAULT = r'''[outfile]
name = update.sp6
path = .


[update]
# 是否挂载文件系统
is_mount = 0

# 是否压缩
is_zip = 0

# 是否需要重启
is_reboot = 1


# 以下是需要打包的文件，数量不限，可自行增加
[file1]
# 0:内核  1:根文件系统  2:boot  3:环境变量  4:命令文件  5:其他文件
type = 0

# 文件名(支持路径)
path = uImage

# 烧写目标地址(支持单位K/M/G)
dest_addr = 1M

# 以下是需要打包的文件，数量不限，可自行增加
[file2]
# 0:内核  1:根文件系统  2:boot  3:环境变量  4:命令文件  5:其他文件
type = 1

# 文件名(支持路径)
path = cramfs.img

# 烧写目标地址(支持单位K/M/G)
dest_addr = 3M

'''

class ConfigClass():
    """merge config"""
    infile_num = 0
    def __init__(self):
        if not os.path.isfile(CONFIG_FILE):
            print('config file not found, create new.')
            with open(CONFIG_FILE, 'w', encoding='utf-8') as new_file:
                new_file.write(CONFIG_FILE_CONTENT_DEFAULT)
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE, encoding='utf-8-sig')
        while self.config.has_section('file' + str(self.infile_num + 1)):
            self.infile_num += 1

    def chk_config(self):
        """chk config"""
        if not self.outfile_cfg().get('path'):
            raise Exception('out file invalid, merge abort.')
        if not self.config.has_section('file1'):
            raise Exception('no input file, merge abort.')

    def outfile_cfg(self):
        """outfile_cfg"""
        return self.config['outfile']

    def update_cfg(self):
        """update_cfg"""
        return self.config['update']

    def infile_cfg(self, file_no):
        """infile_cfg"""
        return self.config['file' + str(file_no)]

CONFIG = ConfigClass()


def get_head():
    """get head"""
    len = (21 + 85*CONFIG.infile_num).to_bytes(4, 'little')
    id = b'\x00'*16
    is_mount = b'\x01' if CONFIG.update_cfg().getboolean('is_mount') else b'\x00'
    is_zip = b'\x01' if CONFIG.update_cfg().getboolean('is_zip') else b'\x00'
    is_reboot = b'\x01' if CONFIG.update_cfg().getboolean('is_reboot') else b'\x00'
    dummy = b'\x00'
    file_num = CONFIG.infile_num.to_bytes(1, 'little')

    infile_info = b''
    for file_cnt in range(CONFIG.infile_num):
        infile_path = os.path.join(CONFIG.infile_cfg(file_cnt + 1).get('path'))
        file_type = int(CONFIG.infile_cfg(file_cnt + 1).get('type'), 0).to_bytes(1, 'little')
        file_name = bytes(os.path.basename(infile_path), encoding='utf-8')
        file_name = (file_name + b'\x00'*24)[:24]
        file_path = b'\x00'*32
        dest_addr_str = CONFIG.infile_cfg(file_cnt + 1).get('dest_addr')
        dest_addr_int = 0
        if dest_addr_str[-1] in ['b', 'B']:
            dest_addr_int = int(dest_addr_str[:-1], 0)
        elif dest_addr_str[-1] in ['k', 'K']:
            dest_addr_int = int(dest_addr_str[:-1], 0) * 1024
        elif dest_addr_str[-1] in ['m', 'M']:
            dest_addr_int = int(dest_addr_str[:-1], 0) * 1024 * 1024
        elif dest_addr_str[-1] in ['g', 'G']:
            dest_addr_int = int(dest_addr_str[:-1], 0) * 1024 * 1024 * 1024
        else:
            dest_addr_int = int(dest_addr_str, 0)
        dest_addr = dest_addr_int.to_bytes(4, 'little')
        zip_len = b'\x00'*4
        raw_len = int(os.path.getsize(infile_path)).to_bytes(4, 'little')
        md5_str = hashcalc.get_md5(infile_path)
        file_md5 = bytes([int(md5_str[x : x+2], 16) for x in range(0, 32, 2)])
        print('file{no}[{path}]:'\
                .format(no=file_cnt+1, path=infile_path))
        print('  type: {typ}, dest_addr: {addr}, raw_len: {len}'\
                .format(typ=int.from_bytes(file_type, 'little')\
                , addr=dest_addr_int, len=int.from_bytes(raw_len, 'little')))
        print('  md5:', md5_str)
        infile_info += file_type + file_name + file_path + dest_addr + zip_len + raw_len + file_md5
    update_info = len + id + is_mount + is_zip + is_reboot + dummy + file_num
    crc = hashcalc.get_crc16(update_info + infile_info).to_bytes(2, 'little')
    return crc + update_info + infile_info


def start_create(out_path=''):
    """main"""
    try:
        out_sp6_file_path = os.path.join(\
            out_path if out_path else CONFIG.outfile_cfg().get('path'),\
            CONFIG.outfile_cfg().get('name'))
        print('out file:', out_sp6_file_path)
        print('mount: ', 'yes' if CONFIG.update_cfg().getboolean('is_mount') else 'no')
        print('zip: ', 'yes' if CONFIG.update_cfg().getboolean('is_zip') else 'no')
        print('reboot: ', 'yes' if CONFIG.update_cfg().getboolean('is_reboot') else 'no')
        print('\ninfile num: ', CONFIG.infile_num)
        with open(out_sp6_file_path, 'wb') as outfile:
            outfile.write(get_head())
            for cnt in range(CONFIG.infile_num):
                infile_path = os.path.join(CONFIG.infile_cfg(cnt + 1).get('path'))
                infile = open(infile_path, 'rb')
                outfile.write(infile.read())
                infile.close()
        return 0
    except Exception:
        traceback.print_exc()
        return -1


def del_outfile(out_path=''):
    """delete outfile"""
    try:
        out_sp6_file_path = os.path.join(\
            out_path if out_path else CONFIG.outfile_cfg().get('path'),\
            CONFIG.outfile_cfg().get('name'))
        if os.path.isfile(out_sp6_file_path):
            os.remove(out_sp6_file_path)
    except Exception:
        traceback.print_exc()
        print('outfile del failed.')

if __name__ == '__main__':
    out_file_path = None
    opts, args = getopt.gnu_getopt(sys.argv[1:], "o:")
    if not args:
        WORKING_PATH = SOFTWARE_PATH
    else:
        WORKING_PATH = args[0]
    for op, value in opts:
        if op == '-o':
            out_file_path = os.path.abspath(value)
    try:
        CONFIG.chk_config()
        if not os.path.isdir(WORKING_PATH):
            raise Exception('ERROR: working path{path} invalid.'.format(path=WORKING_PATH))
        if out_file_path and not os.path.isdir(out_file_path):
            os.makedirs(out_file_path)

        tm_start = time.time()
        print('SP6 Boot Update Creator {ver}({date}).Designed by Kay.'.format(ver=VERSION, date=DATE))
        print('WORKING_PATH:', WORKING_PATH)
        print('CONFIG_FILE:', CONFIG_FILE)
        os.chdir(WORKING_PATH)
        if start_create(out_file_path) == 0:
            print('success')
        else:
            raise Exception('!!FAILED!!')
        print('time use {tm:.1f}s'.format(tm=time.time() - tm_start))
        sys.exit(0)
    except Exception:
        traceback.print_exc()
        os.system('color 47')
        del_outfile(out_file_path)
        time.sleep(3)
        os.system('color 07')
        sys.exit(1)
