from yacs.config import CfgNode as CN
from pyaichtools import Converter
import argparse

parser = argparse.ArgumentParser(description='Encode source code to label and Decode to source')
parser.add_argument('--ql_path', help='path to quality list file', default='test/src/ql.py')
parser.add_argument('--body_path', help='path to source code to test', default='test/src/body.py')
parser.add_argument('--output_path', help='path to output code which decoded', default='test/out/gen.py')

args = parser.parse_args()

header_path = 'test/src/header.py'
footer_path = 'test/src/footer.py'

# change here to test your answer code is right
body_path = args.body_path
output_path = args.output_path

cfg = CN(new_allowed=True)
cfg.header_path = header_path
cfg.footer_path = footer_path
cfg.ql_path = args.ql_path
cfg.var_range = 10
cfg.const_range = 20
cfg.SPT = '/'
temp_converter = Converter(cfg)
label_seq = temp_converter.encode(body_path)
generated_code = temp_converter.decode(label_seq)

with open(output_path, "w") as out_file:
	out_file.write(generated_code)

exec(generated_code)