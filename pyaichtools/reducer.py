from collections import defaultdict
import os
import json
import typing
import libcst as cst
import inspect
import sys
from pyaichtools.utils import *
from treelib import Tree, Node				
import copy
from operator import itemgetter

class Reducer():
	def __init__(self, label_root_path, cst_class_tree_path=None, debug=False):
		with open(os.path.join(label_root_path, "label_dict.json")) as ld_file:
			self.label_dict = json.load(ld_file)
		
		with open(os.path.join(label_root_path, "reverse_label_dict.json")) as rld_file:
			self.reverse_label_dict = json.load(rld_file)
		
		self.range_per_pi = {
			"math": list(range(self.reverse_label_dict["acos"], self.reverse_label_dict["trunc"]+1)),
			"itertools": list(range(self.reverse_label_dict["__loader__"], self.reverse_label_dict["zip_longest"]+1)),
			"QL": list(range(self.reverse_label_dict["0"], self.reverse_label_dict["19"]+1)),
			"NL": list(range(self.reverse_label_dict["100"], self.reverse_label_dict["149"]+1)),
			"var": list(range(self.reverse_label_dict["var0"], self.reverse_label_dict["itertools"]+1))
		}
		self.reverse_range_per_pi = defaultdict(lambda:"None")
		for k, v in self.range_per_pi.items():
			for v_ele in v:
				self.reverse_range_per_pi[v_ele] = k

		self.get_child_node = lambda x: getattr(cst, x).__dict__['__annotations__']
		self.cst_need_child = lambda x: '__annotations__' in getattr(cst, x).__dict__
		self.hard_mask_node = [self.reverse_label_dict["Integer"], self.reverse_label_dict["Float"], self.reverse_label_dict["Imaginary"]]

		if debug:
			self.label = lambda x: x
			self.reverse_label = lambda x: self.label_dict[str(x)]
		else:
			self.label = lambda x: self.reverse_label_dict[x]
			self.reverse_label = lambda x: x

		if cst_class_tree_path is None:
			self.cst_class_tree = self.build_cst_class_tree()

			with open('label/cst_tree_dict.json', "w") as tree_file:
				json.dump(self.cst_class_tree.to_dict(), tree_file)
		else:
			with open(cst_class_tree_path) as tree_file:
				self.cst_class_tree = json.load(tree_file)
			#for k, v in self.cst_class_tree.items():
			#	self.cst_class_tree[k] = 
	
	def build_cst_class_tree(self):
		cst_classes = {cst_class: getattr(cst, cst_class) for cst_class in dir(sys.modules["libcst"]) if inspect.isclass(getattr(cst, cst_class))}
		cst_tree_dict = {}
		for _cst_class in list(cst_classes.values()):
			curr_tree = Tree()
			curr_tree.create_node(tag=_cst_class.__name__, identifier=_cst_class.__name__)
			cst_tree_dict[_cst_class.__name__] = curr_tree
		
		cst_count = 0

		while cst_count != len(cst_tree_dict):
			for curr_tree in list(cst_tree_dict.keys()):
				cst_count+=1
				if hasattr(cst_classes[curr_tree], '__base__'):
					curr_base = cst_classes[curr_tree].__base__.__name__ 
					parent_tree_key = [_tree for _tree in list(cst_tree_dict.keys()) if curr_base in list(cst_tree_dict[_tree].expand_tree())]

					if len(parent_tree_key) != 0:
						parent_tree_key = parent_tree_key[0]
					elif 'libcst' in cst_classes[curr_tree].__base__.__module__.split('.'):
						new_tree = Tree()
						cst_classes[curr_base] = cst_classes[curr_tree].__base__
						new_tree.create_node(curr_base, curr_base)
						cst_tree_dict[curr_base] = new_tree
						parent_tree_key = curr_base
					else:
						continue

					curr_parent_tree = cst_tree_dict[parent_tree_key]
					curr_parent_tree.paste(curr_base, cst_tree_dict[curr_tree])
					#curr_parent_tree.add_node(cst_tree_dict[curr_tree].get_node(curr_tree), parent=curr_base)
					del cst_tree_dict[curr_tree]
					cst_count = 0
					break
		
		return cst_tree_dict["CSTNode"]
	
	def get_candidate(self, parent_label, curr_attr, pi_label, curr_label):
		seq_label = []

		if parent_label == 'Integer':
			assert pi_label in ["QL", "NL"]
			seq_label = [self.reverse_label(idx_label) for idx_label in self.range_per_pi[pi_label]]
		elif curr_attr is str:
			# curr node need string node as child. This is only the case when it is variable name or package name.
			assert pi_label in ["math", "itertools", "var"]
			seq_label = [self.reverse_label(idx_label) for idx_label in self.range_per_pi[pi_label]]
		elif type(curr_attr) == typing._GenericAlias:
			if curr_attr._name == "Sequence":
				key_type_info = "Sequence"
			for attr_ele in curr_attr.__args__:
				if 'libcst' in attr_ele.__module__:
					seq_label.extend([self.label(node.tag) for node in self.cst_class_tree.leaves(attr_ele.__name__)])
		else:
			seq_label = [self.label(node.tag) for node in self.cst_class_tree.leaves(curr_attr.__name__)]

		if curr_label is not "Index":
			seq_label = self.remove_hmn(seq_label)

		return seq_label
	
	def remove_hmn(self, candidate_list):
		for hmn in self.hard_mask_node:
			if hmn in candidate_list:
				candidate_list.remove(self.reverse_label(hmn))
		return candidate_list
		
	def reduce_out(self, parent_id_list, parent_child_idx, curr_id_list):
		parent_label = list(itemgetter(*[str(v) for v in parent_id_list])(self.label_dict))
		curr_label = list(itemgetter(*[str(v) for v in curr_id_list])(self.label_dict))
		pi_label = list(itemgetter(*curr_id_list)(self.reverse_range_per_pi))

		# predicted cst node which need child node, return possible prediction as dictionary

		attr_list = []
		for pci, p_label in zip(parent_child_idx, parent_label):
			cnt = 0
			curr_attr = None
			curr_child_node = list(self.get_child_node(p_label).items())
			curr_child_node.reverse()
			for k, v in curr_child_node:
				if k in LIBCST_INTERST_ATTR:
					cnt += 1
					if cnt == pci:
						curr_attr = v
						break
			attr_list.append(curr_attr)

		return [
		    self.get_candidate(pl, al, pi, cl)
		    for pl, al, pi, cl in zip(parent_label, attr_list, pi_label, curr_label)
		]


if __name__ == '__main__':
	#test_reducer = Reducer("label", "label/cst_tree_dict.json")
	test_reducer = Reducer("label", debug=False)
	#child_dict = test_reducer.reduce_out(test_reducer.reverse_label_dict["If"], 1, test_reducer.reverse_label_dict["Comparison"])
	parent_label = [test_reducer.reverse_label_dict[v] for v in ["Name", "Integer", "For"]]
	curr_label = [test_reducer.reverse_label_dict[v] for v in ["var0", "5", "Tuple"]]
	child_idx = [1, 1, 3]
	child_dict = test_reducer.reduce_out(parent_label, child_idx, curr_label)
	print(child_dict)
	#print(child_dict)