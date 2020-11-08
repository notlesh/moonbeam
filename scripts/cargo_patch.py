import copy
import toml
import sys
import errno
import os
import subprocess as sp
import shutil
import glob

to_replace_with = [{"repo": "https://github.com/purestake/frontier", "branch": "v0.2-hotfixes"},
				   {"repo": "https://github.com/purestake/substrate", "branch": "tgmichel-rococo-branch"}]
root_cargo_file = "../node/standalone/Cargo.toml"
clones_leaf_dir_name = "patches_git_clones"

root_cargo_path = os.path.dirname(os.path.realpath(root_cargo_file))
clones_dir = os.path.join(root_cargo_path, clones_leaf_dir_name)

with open(root_cargo_file) as f:
	file_data = f.read()

original_file_data = copy.deepcopy(file_data)


def compare_repos_links(repo1, repo2):
	return repo1 == repo2


def mkdir_p(path):
	try:
		os.makedirs(path)
	except OSError as exc:
		if exc.errno == errno.EEXIST and os.path.isdir(path):
			pass
		else:
			raise


def generic_cmd_call(cmd):
	call = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
	output, error = call.communicate()
	if call.returncode != 0:
		raise IOError("Call '%s' threw an error: %s" % (" ".join(cmd), error.decode()))


def git_checkout_branch_in_curr_dir(branch_name):
	cmd = ["git", "checkout", branch_name]
	generic_cmd_call(cmd)


def git_clone_in_curr_dir(url):
	cmd = ["git", "clone", url]
	generic_cmd_call(cmd)


def get_leaf_dir_from_git_url(url: str):
	if len(url.strip("")) == 0:
		raise ValueError("Invalid url to get leaf of: " + url)
	split_url = url.split("/")
	if len(split_url[-1].strip("")) > 0:
		return split_url[-1].strip("")
	if len(split_url) > 1 and len(split_url[-2].strip("")) > 0:
		return split_url[-2].strip("")
	raise ValueError("Invalid url with invalid split pattern to get leaf of: " + url)


def clone_repos(repos_to_replace_with, force=False):
	original_curr_dir = os.getcwd()
	try:
		for repo_info in repos_to_replace_with:
			mkdir_p(clones_dir)
			os.chdir(clones_dir)
			clone_target_dir = get_leaf_dir_from_git_url(repo_info['repo'])
			# reclone only if "force" is true
			if os.path.isdir(clone_target_dir):
				if not force:
					continue
				else:
					shutil.rmtree(clone_target_dir)
			# clone
			git_clone_in_curr_dir(repo_info['repo'])
			# checkout the branch, if exists
			if 'branch' in repo_info:
				os.chdir(os.path.join(clones_dir, clone_target_dir))
				git_checkout_branch_in_curr_dir(repo_info['branch'])
	finally:
		# restore current dir in case of an exception raised
		os.chdir(original_curr_dir)


def get_toml_dependencies(path_to_toml):
	parsed_file = toml.load(path_to_toml)
	if 'dependencies' in parsed_file:
		return parsed_file['dependencies']
	else:
		sys.stderr.write("File {} does not contain a dependencies section".format(path_to_toml))
		return {}

def get_all_toml_dependencies(path_to_root_toml):
	result = get_toml_dependencies(path_to_root_toml)
	cargo_files = get_all_cargo_files_in_subdir("src")
	for cargo_file in cargo_files:
		result.update(get_toml_dependencies(cargo_file))
	return result


def get_toml_project_name(path_to_toml):
	# print("Getting project name:", path_to_toml)
	parsed_file = toml.load(path_to_toml)
	try:
		return parsed_file['package']['name']
	except KeyError as e:
		if not 'workspace' in parsed_file:
			sys.stderr.write(
				"File {} does not contain a package with a name under it".format(path_to_toml))


def create_replaceable_dependencies(parsed_cargo_file_dependencies, repos_to_replace_with):
	dependencies_found_to_replace = {}
	for k in parsed_cargo_file_dependencies:
		val = parsed_cargo_file_dependencies[k]
		if 'git' in val:
			# check all given dependencies to replace
			for t in repos_to_replace_with:
				if compare_repos_links(t['repo'], val['git']) and t['branch'] == val['branch']:
					dependencies_found_to_replace[k] = val
		# print(k, parsed_cargo_file_dependencies[k], 'git' in dependencies_dict[k])
	return dependencies_found_to_replace


def get_all_cargo_files_in_subdir(leaf_dir_name):
	original_curr_dir = os.getcwd()
	try:
		os.chdir(clones_dir)
		return [os.path.abspath(file) for file in
				glob.glob(leaf_dir_name + "/**/Cargo.toml", recursive=True)]

	finally:
		# restore current dir in case of an exception raised
		os.chdir(original_curr_dir)


def find_project_dir_by_name_in_cargo_files(cargo_files_list, proj_name):
	for file in cargo_files_list:
		package_name = get_toml_project_name(file)
		if package_name == proj_name:
			return os.path.dirname(os.path.abspath(file))
	raise ValueError(
		"Could not find a project that matches name " + proj_name + " in " + str(cargo_files_list))


def create_patch_toml_lines(deps_to_replace, repos_to_replace_with):
	result = {}
	for dep_key in deps_to_replace:
		# print(deps_to_replace[dep_key])
		for repo_info_key in repos_to_replace_with:
			if compare_repos_links(deps_to_replace[dep_key]['git'],
								   repo_info_key['repo']):
				entry = deps_to_replace[dep_key]
				repo_link = deps_to_replace[dep_key]['git']

				# locate all cargo files in git repo
				clone_leaf_target_dir = get_leaf_dir_from_git_url(repo_info_key['repo'])
				cargo_files = get_all_cargo_files_in_subdir(clone_leaf_target_dir)
				# get package name (either from leaf dir name, or explicitly mentioned)
				package_name = dep_key
				if 'package' in entry:
					package_name = entry['package']
				# print("Parsing:", package_name)
				project_cargo_path = find_project_dir_by_name_in_cargo_files(cargo_files,
																			 package_name)
				# print("project path:", project_cargo_path)
				# print("Repo:", entry)
				# print("Targets:", cargo_files)

				key_vals = ['path = "{}"'.format(project_cargo_path)]
				# TODO: make this work! You should read all Cargo.toml files
				# that are cloned, and point the path to that directory
				for entry_key in entry:
					# add everything except for git and branch
					if entry_key != 'git' and entry_key != 'branch':
						key_val = entry_key
						key_val += " = "
						key_val += '"' + entry[entry_key] + '"'
						key_vals.append(key_val)

				final_line = dep_key
				final_line += " = "
				final_line += "{"
				final_line += " " if len(key_vals) > 0 else ""
				final_line += ", ".join(key_vals)
				final_line += " " if len(key_vals) > 0 else ""
				final_line += "}"

				# add the patch group
				if repo_link not in result:
					result[repo_link] = []
				result[repo_link].append(final_line)
	return result


def make_patch_lines(dict_with_patch_contents: dict):
	result = ''
	for link in dict_with_patch_contents:
		result += '[patch."{}"]\n'.format(link)
		for patch_line in dict_with_patch_contents[link]:
			result += patch_line + "\n"
		result += "\n"
	return result


clone_repos(to_replace_with, False)
deps_replaceable = create_replaceable_dependencies(
	get_all_toml_dependencies(root_cargo_file),
	to_replace_with)
print("deps:", deps_replaceable)
patch_lines = create_patch_toml_lines(deps_replaceable, to_replace_with)
print(patch_lines)
print(make_patch_lines(patch_lines))
