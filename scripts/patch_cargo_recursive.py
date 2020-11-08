import copy
import toml
import sys
import errno
import os
import subprocess as sp
import shutil
import glob

# to_replace_with = [{"repo": "https://github.com/purestake/frontier", "branch": "v0.2-hotfixes"},
# 				   {"repo": "https://github.com/purestake/substrate", "branch": "tgmichel-rococo-branch"}]
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
	"""
	equivalent to unix's `mkdir -p`
	"""
	try:
		os.makedirs(path)
	except OSError as exc:
		if exc.errno == errno.EEXIST and os.path.isdir(path):
			pass
		else:
			raise


def generic_cmd_call(cmd):
	"""
	Calls a command in the system, prints stdout and stderr, and raises an error on failure
	"""
	call = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
	output, error = call.communicate()
	if call.returncode != 0:
		raise IOError("Call '%s' threw an error: %s" % (" ".join(cmd), error.decode()))


def git_checkout_branch_in_curr_dir(branch_name):
	cmd = ["git", "checkout", branch_name]
	generic_cmd_call(cmd)


def git_clone_in_curr_dir(url, target_dir=None):
	if target_dir is None:
		cmd = ["git", "clone", url]
	else:
		cmd = ["git", "clone", url, target_dir]
	generic_cmd_call(cmd)


def get_leaf_dir_from_git_url(url_orig: str, branch: str):
	"""
	Creates a reproducible directory name from a given repository and branch
	"""
	if "github.com" in url_orig and url_orig.endswith(".git"):
		url_orig = url_orig[:-4]
	url = url_orig.split("://")[-1]
	if len(url.strip("")) == 0:
		raise ValueError("Invalid url to get leaf of: " + url)
	if url[-1] == '/':
		url = url[:-1]
	return url.replace("/", "_").replace(".", "_") + "_" + branch


def clone_all_repos(starting_cargo_file, force=False):
	"""
	clones all repositories recursively
	:param starting_cargo_file:
	:param force: force recloning even if the repo exists
	"""
	original_curr_dir = os.getcwd()
	deps = get_toml_dependencies(starting_cargo_file)
	# extract all git repos links
	deps_repos = {}
	for dep_name in deps:
		repo_link = ""
		if "git" in deps[dep_name]:
			repo_link = deps[dep_name]['git']
		repo_branch = 'master'
		if "branch" in deps[dep_name]:
			repo_branch = deps[dep_name]['branch']
		if repo_link != "":
			deps_repos[repo_link] = repo_branch

	# do the cloning and checkouts
	try:
		cloned_target_dirs = []
		for dep_link in deps_repos:
			dep_branch = deps_repos[dep_link]
			mkdir_p(clones_dir)
			os.chdir(clones_dir)
			clone_target_dir = get_leaf_dir_from_git_url(dep_link, dep_branch)
			cloned_target_dirs.append(clone_target_dir)
			# reclone only if "force" is true
			if os.path.isdir(clone_target_dir):
				if not force:
					continue
				else:
					shutil.rmtree(clone_target_dir)
			# clone
			git_clone_in_curr_dir(dep_link, clone_target_dir)
			# checkout the branch, if exists
			if dep_branch != 'master':
				p = os.path.join(clones_dir, clone_target_dir)
				os.chdir(p)
				git_checkout_branch_in_curr_dir(dep_branch)

		os.chdir(clones_dir)
		for cloned_target_dir in cloned_target_dirs:
			for cargo_file in get_all_cargo_files_in_subdir(cloned_target_dir):
				parsed_file = toml.load(cargo_file)
				# TODO: find a mechanism to skip all unnecessary cargo files
				# TODO: workspace files is only one kind of the files to be skipped
				if 'workspace' in parsed_file:
					continue  # skip workspace cargo files
				clone_all_repos(cargo_file, force)
	finally:
		# restore current dir in case of an exception raised
		os.chdir(original_curr_dir)


def get_toml_dependencies(path_to_toml):
	parsed_file = toml.load(path_to_toml)
	result = {}
	if 'dependencies' in parsed_file:
		result.update(parsed_file['dependencies'])
	else:
		sys.stderr.write("File {} does not contain a dependencies section\n".format(path_to_toml))
	if 'dev-dependencies' in parsed_file:
		result.update(parsed_file['dev-dependencies'])
	return result


def get_toml_project_name(path_to_toml):
	# print("Getting project name:", path_to_toml)
	parsed_file = toml.load(path_to_toml)
	try:
		return parsed_file['package']['name']
	except KeyError as e:
		if not 'workspace' in parsed_file:
			sys.stderr.write(
				"File {} does not contain a package with a name under it\n".format(path_to_toml))


def create_replacing_dependencies(parsed_cargo_file_dependencies):
	"""
	Filters all dependencies and returns the ones with 'git' entry
	"""
	dependencies_found_to_replace = {}
	for k in parsed_cargo_file_dependencies:
		val = parsed_cargo_file_dependencies[k]
		if 'git' in val:
			# check all given dependencies to replace
			dependencies_found_to_replace[k] = val
	# print(k, parsed_cargo_file_dependencies[k], 'git' in dependencies_dict[k])
	return dependencies_found_to_replace


def get_all_cargo_files_in_subdir(leaf_dir_name):
	"""
	searches for all cargo files in the given subdirectory
	perhaps a better filter should be implemented to exclude
	cargo files that have no dependencies list
	:param leaf_dir_name:
	"""
	original_curr_dir = os.getcwd()
	try:
		os.chdir(clones_dir)
		return [os.path.abspath(file) for file in
				glob.glob(leaf_dir_name + "/**/Cargo.toml", recursive=True)]

	finally:
		# restore current dir in case of an exception raised
		os.chdir(original_curr_dir)


def find_project_dir_by_name_in_cargo_files(cargo_files_list, proj_name):
	"""
	Given a list of cargo files, find which cargo file has the `name` entry given
	"""
	for file in cargo_files_list:
		package_name = get_toml_project_name(file)
		if package_name == proj_name:
			return os.path.dirname(os.path.abspath(file))
	raise ValueError(
		"Could not find a project that matches name " + proj_name + " in " + str(cargo_files_list))


def as_cargo_type(value):
	"""
	toml package in python converts toml content to a dict
	this function is used to convert types back, since they have
	to be converted in different ways
	"""
	if type(value) == bool:
		return "true" if value else "false"
	elif type(value) == int:
		return str(value)
	else:
		return '"{}"'.format(str(value))


def create_patch_toml_lines(deps_to_replace):
	"""
	Given a list of dependencies, create a list of lines that will be used to patch
	a cargo file
	"""
	result = {}
	for dep_key in deps_to_replace:
		# print(deps_to_replace[dep_key])
		# for repo_info_key in repos_to_replace_with:
		if True:
			# if compare_repos_links(deps_to_replace[dep_key]['git'],
			# 					   repo_info_key['repo']):
			if True:
				entry = deps_to_replace[dep_key]
				repo_link = deps_to_replace[dep_key]['git']
				repo_branch = deps_to_replace[dep_key]['branch'] if \
					"branch" in deps_to_replace[dep_key] else "master"

				# locate all cargo files in git repo
				clone_leaf_target_dir = get_leaf_dir_from_git_url(deps_to_replace[dep_key]['git'], repo_branch)
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

				# instantiate key/value pairs for patch lines, start with "path"
				key_vals = ['path = "{}"'.format(project_cargo_path)]
				# TODO: make this work! You should read all Cargo.toml files
				# that are cloned, and point the path to that directory
				for entry_key in entry:
					# add everything except for git and branch
					if entry_key != 'git' and entry_key != 'branch':
						key_val = entry_key
						key_val += " = "
						key_val += as_cargo_type(entry[entry_key])
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


def write_patch_lines(dict_with_patch_contents: dict):
	"""
	Given a list of lines, format these lines into a final string
	that can be put in a cargo file
	"""
	result = ''
	for link in dict_with_patch_contents:
		result += '[patch."{}"]\n'.format(link)
		for patch_line in dict_with_patch_contents[link]:
			result += patch_line + "\n"
		result += "\n"
	return result


def get_cargo_files_after_clone():
	"""
	From global variables and successful clones, collect all the cargo files,
	from which dependencies is to be collected
	"""
	cargo_files = [root_cargo_file]
	root_cargo_files_of_dependencies = glob.glob(clones_dir + "/*/Cargo.toml")
	for cf in root_cargo_files_of_dependencies:
		cargo_files.extend(get_all_cargo_files_in_subdir(os.path.dirname(cf)))
	return cargo_files


def get_toml_dependencies_from_multiple_cargo_files(cargo_files_list):
	"""
	given a list of cargo files, loop over all of them, and get all dependencies
	"""
	result = {}
	for cf in cargo_files_list:
		deps = get_toml_dependencies(cf)
		for dep in deps:
			if 'git' in deps[dep]:
				result[dep] = deps[dep]
	return result


clone_all_repos(root_cargo_file, False)
cargo_files = get_cargo_files_after_clone()
dependencies_dict = get_toml_dependencies_from_multiple_cargo_files(cargo_files)
print(dependencies_dict)
deps_replaceable = create_replacing_dependencies(dependencies_dict)
print("deps:", deps_replaceable)
patch_lines = create_patch_toml_lines(deps_replaceable)
print("patch lines:", patch_lines)
print(write_patch_lines(patch_lines))
