import libcst as cst
import sys
import inspect
import json
from treelib import Tree, plugins

LIBCST_INTERST_ATTR = [
    "body",
	"value",
	"func",
	"targets",
	"args",
	"target",
	"test",
	"comparisons",
	"operator",
	"comparator",
	"left",
	"names",
	"name",
	"attr",
	"right",
	"elements",
	"iter",
	"slice"
]

VAR_PREFIX = "var{}"
CONST_PREFIX = "const{}"
PROBLEM_INFO_PREFIX = "QL"
MAX_QUANTITY_LEN = 20

class Converter:
	def __init__(self, cfg):
		with open(cfg.header_path) as header_file:
			header_file = header_file.read()
			self.header = cst.parse_module(header_file)

		with open(cfg.ql_path) as ql_file:
			ql_file = ql_file.read()
			self.quality_list = cst.parse_module(ql_file)

		with open(cfg.footer_path) as footer_file:
			footer_file = footer_file.read()
			self.footer = cst.parse_module(footer_file)

		self.interest_attr_list = LIBCST_INTERST_ATTR
		self.var_list = [VAR_PREFIX.format(i) for i in range(cfg.var_range)] + ["result"]
		self.const_list = [CONST_PREFIX.format(i) for i in range(cfg.const_range)]
		self.tree_spt_list = ['nodest', 'nodeen', 'argst', 'argen']

		self.label_dict, self.reverse_label_dict, self.LABEL_LIMIT = \
			self.generate_label_dict(self.var_list, self.const_list, self.tree_spt_list, PROBLEM_INFO_PREFIX, MAX_QUANTITY_LEN)
		

		#if you want to generate new label dictionary, uncomment these lines
		"""
		with open('label_dict.json', 'w') as ld:
			json.dump(self.label_dict, ld)
		
		with open('reverse_label_dict.json', 'w') as rld:
			json.dump(self.reverse_label_dict, rld)
		"""
		
		self.SPT = cfg.SPT
		self.attach_code = lambda x: self.header.body + self.quality_list.body + x + self.footer.body
		
	def generate_label_dict(self, var_list, const_list, tree_spt_list, pi_prefix, max_qunatity_len):
		libcst_class_list = [
			'{}'.format(name)
			for name, obj in inspect.getmembers(sys.modules['libcst'])
			if inspect.isclass(obj)
		]
		libcst_class_list.sort()

		math_func_list = [
			'{}'.format(name)
			for name, obj in inspect.getmembers(sys.modules['math'])
			if inspect.isbuiltin(obj)
		]
		math_func_list.sort()
		math_func_list.append("math")

		itertools_class_list = [
			'{}'.format(name)
			for name, obj in inspect.getmembers(sys.modules['itertools'])
			if inspect.isclass(obj)
		]
		itertools_class_list.sort()
		itertools_class_list.append('itertools')

		whole_label_list = libcst_class_list + math_func_list + itertools_class_list + var_list + const_list + tree_spt_list
		whole_label_list.append(pi_prefix)
		LABEL_LIMIT = len(whole_label_list)
		whole_label_list.extend(list(range(max_qunatity_len)))

		label_dict = {k: v for k, v in zip(range(len(whole_label_list)), whole_label_list)}
		reverse_label_dict = {k: v for k, v in zip(whole_label_list, range(len(whole_label_list)))}

		return label_dict, reverse_label_dict, LABEL_LIMIT
			
	def cst_to_tree(self, parsed_cst, cst_tree, parent_id=None, attr=None):

		if not hasattr(parsed_cst, '__module__'):
			curr_node = cst_tree.create_node(str.join(self.SPT, [attr, parsed_cst]), parent=parent_id)
			return
		elif attr is None:
			curr_node = cst_tree.create_node(type(parsed_cst).__name__, parent=parent_id)
		else:
			curr_node = cst_tree.create_node(str.join(self.SPT, [attr, type(parsed_cst).__name__]), parent=parent_id)

		for interest_attr in dir(parsed_cst):
			if interest_attr in self.interest_attr_list:
				if type(getattr(parsed_cst, interest_attr)) in [list ,tuple]:
					for attr_ele in getattr(parsed_cst, interest_attr):
						self.cst_to_tree(attr_ele, cst_tree, parent_id=curr_node.identifier, attr=interest_attr)
				else:
					self.cst_to_tree(getattr(parsed_cst, interest_attr), cst_tree, parent_id=curr_node.identifier, attr=interest_attr)
		return cst_tree

	def tree_to_seq(self,ann_tree, seq=[]):
		curr_child = ann_tree.children(ann_tree.root)
		curr_tag = ann_tree.get_node(ann_tree.root).tag.split(self.SPT)
		if len(curr_child) == 0:
			curr_seq = ["nodest","nodeen",curr_tag[1],]
		else:
			curr_seq = ["nodest"]
			prev_attr = curr_child[0].tag.split(self.SPT)[0]
			curr_seq.append("argst")
			for child_node in curr_child:
				curr_attr = child_node.tag.split(self.SPT)[0]
				if prev_attr != curr_attr:
					curr_seq.extend(["argen", "argst"])
				curr_seq = self.tree_to_seq(ann_tree.subtree(child_node.identifier), curr_seq)
			curr_seq.append("argen")
			curr_seq.append("nodeen")
			#curr_seq.append(str.join(SPT, curr_tag))
			curr_seq.append(curr_tag[1])
		seq.extend(curr_seq)
		return seq

	def div_by_attr(self, ann_seq):
		attr_list = []
		attr_cnt = 0
		st = 0
		for id, ann_ele in enumerate(ann_seq):
			if ann_ele is "argst":
				attr_cnt += 1
			elif ann_ele is "argen":
				attr_cnt -= 1
			if attr_cnt == 0:
				attr_list.append(ann_seq[st:id+1])
				st = id+1
		return attr_list

	def div_by_node(self, node_seq):
		node_list = []
		node_cnt = 0
		st = 0
		for id, ann_ele in enumerate(node_seq):
			if ann_ele is "nodest":
				node_cnt += 1
			elif ann_ele is "nodeen":
				node_cnt -= 1
				if node_cnt == 0:
					node_list.append(node_seq[st:id+2])
					st = id+2
		return node_list

	def seq_to_tree(self, ann_seq, root_tree, parent_id=None, attr="root"):
		if len(ann_seq):
			node_seq_list = self.div_by_node(ann_seq)
			for node_seq in node_seq_list:
				curr_tag = node_seq[-1]
				curr_node = root_tree.create_node(str.join(self.SPT, [attr,curr_tag]), parent=parent_id)
				if hasattr(cst, curr_tag):
					attr_list = [attr for attr in dir(getattr(cst, curr_tag)) if attr in self.interest_attr_list]
					attr_seq_list = self.div_by_attr(node_seq[1:-2])
					for attr_ele, attr_seq in zip(attr_list, attr_seq_list):
						root_tree = self.seq_to_tree(attr_seq[1:-1], root_tree, curr_node.identifier, attr_ele)
		return root_tree

	def tree_to_cst(self, ann_tree, cst_node=None):
		curr_node = ann_tree.get_node(ann_tree.root)
		arg_name, class_name = curr_node.tag.split(self.SPT)

		if not hasattr(cst, class_name):
			return class_name

		curr_class = getattr(cst, class_name)

		check_sequence = lambda x: hasattr(curr_class.__dict__['__annotations__'][x], '_name') and curr_class.__dict__['__annotations__'][x]._name is 'Sequence'

		arg_dict = {
			attr: [] if check_sequence(attr) else None
			for attr in dir(curr_class)
			if attr in self.interest_attr_list
		}

		for child_node in ann_tree.children(ann_tree.root):
			child_arg_name, child_class_name = child_node.tag.split(self.SPT)
			if check_sequence(child_arg_name):
				arg_dict[child_arg_name].append(self.tree_to_cst(ann_tree.subtree(child_node.identifier)))
			else:
				arg_dict[child_arg_name] = self.tree_to_cst(ann_tree.subtree(child_node.identifier))
		return curr_class(**arg_dict)

	def label_seq(self, encoded_seq, problem_info=None):
		labeled_seq = []
		for id, ann_ele in enumerate(encoded_seq):
			if str.isdigit(ann_ele):
				labeled_seq.append(int(ann_ele) + self.LABEL_LIMIT)
			else:
				labeled_seq.append(self.reverse_label_dict[ann_ele])

		return labeled_seq	
	
	def unlabel_seq(self, labeled_seq, problem_info=None):
		encoded_seq = []
		for label_ele in labeled_seq:
			if label_ele >= self.LABEL_LIMIT:
				encoded_seq.append(str(label_ele - self.LABEL_LIMIT))
			else:
				encoded_seq.append(self.label_dict[label_ele])
		return encoded_seq

	def encode(self, source_path, problem_info=None):
		with open(source_path) as body_file:
			body_file = body_file.read()
			body_cst = cst.parse_module(body_file)
		
		essential_tree = Tree()
		essential_tree = self.cst_to_tree(body_cst, essential_tree, attr="root")

		encoded_seq = []
		encoded_seq = self.tree_to_seq(essential_tree, encoded_seq)

		labeled_seq = self.label_seq(encoded_seq, problem_info)

		return labeled_seq

	def decode(self, labeled_seq, problem_info=None):
		decoded_seq = self.unlabel_seq(labeled_seq, problem_info)

		recovered_tree = Tree()
		recovered_tree = self.seq_to_tree(decoded_seq, recovered_tree)
		
		recovered_cst = self.tree_to_cst(recovered_tree)
		recovered_module = cst.Module(body=self.attach_code(recovered_cst.body))		

		generated_code = cst.Module([]).code_for_node(recovered_module)

		return generated_code


if __name__ == '__main__':
	from yacs.config import CfgNode as CN
	cfg = CN(new_allowed=True)
	cfg.header_path = 'test/src/header.py'
	cfg.footer_path = 'test/src/footer.py'
	cfg.var_range = 10
	cfg.const_range = 20
	cfg.SPT = '/'
	temp_converter = Converter(cfg)
	label_seq = temp_converter.encode(
		'test/src/body.py'
	)
	print(label_seq)
	generated_code = temp_converter.decode(label_seq)

	with open('test/out/gen.py', "w") as out_file:
		out_file.write(generated_code)