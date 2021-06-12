import os
import json
import libcst as cst
import inspect
import sys
from pyaichtools.utils import *
from treelib import Tree, Node				
import copy

class Reducer():
	def __init__(self, label_root_path, cst_class_tree_path=None):
		with open(os.path.join(label_root_path, "label_dict.json")) as ld_file:
			self.label_dict = json.load(ld_file)
		
		with open(os.path.join(label_root_path, "reverse_label_dict.json")) as rld_file:
			self.reverse_label_dict = json.load(rld_file)
		
		self.get_child_node = lambda x: getattr(cst, x).__dict__['__annotations__']
		self.cst_need_child = lambda x: '__annotations__' in getattr(cst, x).__dict__
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
					print(curr_base)
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
		
	def reduce_out(self, curr_id):
		curr_label = self.label_dict[str(curr_id)]
		#none_debug_label = lambda x: self.reverse_label_dict[x]
		debug_label = lambda x: x

		child_dict = {}

		if hasattr(cst, curr_label) and self.cst_need_child(curr_label):
			# predicted cst node which need child node, return possible prediction as dictionary
			child_dict = {k: v for k, v in self.get_child_node(curr_label).items() if k in LIBCST_INTERST_ATTR}
			for k, v in child_dict.items():
				key_type_info = "Object"
				candidate_list = []

				if not hasattr(cst, v):
					# curr node need value node as child. This is only the case when it is index or variable name.
					if True:
						pass

				elif hasattr(v, '_name') and v._name == 'Sequence':
					key_type_info = "Sequence"
					for v_ele in v.__args__:
						candidate_list.extend([debug_label(node.tag) for node in self.cst_class_tree.leaves(v_ele.__name__)])
				else:
					candidate_list.extend([debug_label(node.tag) for node in self.cst_class_tree.leaves(v.__name__)])
				child_dict[k] = [key_type_info, candidate_list]
			print(child_dict)

		return child_dict



if __name__ == '__main__':
	#test_reducer = Reducer("label", "label/cst_tree_dict.json")
	test_reducer = Reducer("label")
	test_reducer.reduce_out(107)