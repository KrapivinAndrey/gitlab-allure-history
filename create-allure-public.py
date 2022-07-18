import glob
import os
import shutil
import subprocess
from distutils.dir_util import copy_tree

from gitlab import Gitlab

INDEX_TEXT_START = """<!DOCTYPE html>
<html>
<head>
    <link href="https://avatars.githubusercontent.com/u/5879127?s=64&v=4" rel="icon" type="image/x-icon" />
    <title>Index of {folderPath}</title>
</head>
<body>
    <h2>Index of {folderPath}</h2>
    <hr>
    <ul>
        <li>
            <a href='../'>../</a>
        </li>
"""
INDEX_TEXT_END = """
    </ul>
</body>
</html>
"""

# region helpers

def __translit(instr):
    symbols = (
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
        "abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA",
    )

    tr = {ord(a): ord(b) for a, b in zip(*symbols)}
    return instr.translate(tr)


def __prepare_name(branch_name):
    return __translit(branch_name).replace("/", "_")


def __index_folder(path_):
    print("Indexing: " + path_ + "/")
    # Getting the content of the folder
    files = os.listdir(path_)
    # If Root folder, correcting folder name
    root = path_
    if path_.startswith("public"):
        root = path_.replace("public", "gitlab-allure-history")
    index_text = INDEX_TEXT_START.format(folderPath=root)
    for file in sorted(files):
        # Avoiding index.html files
        if file != "index.html":
            index_text += (
                "\t\t<li>\n\t\t\t<a href='" + file + "'>" + file + "</a>\n\t\t</li>\n"
            )
    index_text += INDEX_TEXT_END
    # Create or override previous index.html
    # Save indexed content to file
    with open(path_ + "/index.html", "w") as index:
        index.write(index_text)


def __findReplace(directory, find, extension="txt"):
    length_to_replace = len(find) // 2
    replace = find[:-length_to_replace] + "*" * length_to_replace
    for_work = set()
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(f".{extension}"):
                filepath = os.path.join(root, file)
                for_work.add(filepath)

    for filepath in for_work:
        with open(filepath, encoding="utf-8-sig") as file:
            s = file.read()
        if s.find(find):
            s = s.replace(find, replace)
            with open(filepath, "w", encoding="utf-8-sig") as file:
                file.write(s)


def __get_all_secrets():
    result = set()
    id = os.environ.get("CI_PROJECT_ID")
    project = gl.projects.get(id)

    vl = project.variables.list()
    for variable in vl:
        result.add(variable.value)

    for group in project.groups.list():
        vl = gl.groups.get(group.id).variables.list()
        for variable in vl:
            result.add(variable.value)

    return result

# endregion

public = os.path.abspath(f"./{os.environ['CI_PROJECT_NAME']}/public")
allure = os.path.abspath(os.environ["ALLURE_REPORTS"])
report = f"pipeline_{os.environ['CI_PIPELINE_ID']}"
branch = __prepare_name(os.environ["CI_COMMIT_REF_NAME"])
branch_dir = os.path.join(public, branch)

gl = Gitlab(
        "https://" + os.environ["CI_SERVER_HOST"],
        private_token=os.environ["JENKINS1C_GITLAB_API_TOKEN"],
        per_page=50
    )
gl.auth()


def clear_old_branches():
    print("Clear old branches")

    project = gl.projects.get(os.environ["CI_PROJECT_ID"])
    print("Actual branches")
    for x in project.branches.list():
        print(f"> {x.name}")
    branches = [__prepare_name(x.name) for x in project.branches.list()]

    for x in os.listdir(public):
        if x not in branches and os.path.isdir(os.path.join(public, x)):
            print(f"Delete old branch folder {x}")
            shutil.rmtree(os.path.join(public, x))


def prepare_directory():
    history = os.path.join(branch_dir, "history")
    allure_history = os.path.join(allure, "history")
    if os.path.exists(history):
        copy_tree(history, allure_history)
    else:
        print("No history")

    print("Create executor info")
    with open(os.path.join(allure, "executor.json"), "w+") as f:
        pages_url = os.environ["CI_PAGES_URL"]
        f.write(
            '{"name":"GitLabCI","type":"gitlab","reportName":"Allure Report with history",\n'
        )
        f.write(f'"reportUrl":"{pages_url}/{branch}/{report}/",\n')
        build_url = os.environ["CI_PIPELINE_URL"]
        f.write(f'"buildUrl":"{build_url}",\n')
        build_name = os.environ["CI_PIPELINE_ID"]
        build_order = os.environ["CI_PIPELINE_IID"]
        f.write(
            f'"buildName":"GitLab Job Run {build_name}","buildOrder":"{build_order}"'
        )
        f.write("}")


def clear_old_reports():
    list_of_files = filter(os.path.isdir, glob.glob(os.path.join(branch_dir, "pipeline*")))
    list_of_files = sorted(list_of_files, key=os.path.getmtime)

    if len(list_of_files) < 10:
        return
    print("Clear old reports")
    for report_dir in list_of_files[:-10]:
        print(f"Remove {report_dir}")
        shutil.rmtree(os.path.join(report_dir))


def clear_secrets():
    print("Clear secrets")

    for variables in __get_all_secrets():
        __findReplace(allure, variables, "json")
        __findReplace(allure, variables, "html")
        __findReplace(allure, variables, "xml")


def create_allure():
    print("Create Allure report")
    subprocess.run(["allure", "generate", allure, "-o", report])


def copy_folders():
    print("Copy report to destinations")
    if not os.path.exists(branch_dir):
        os.makedirs(branch_dir)
    copy_tree(report, os.path.join(branch_dir, report))
    copy_tree(os.path.join(report, "history"), os.path.join(branch_dir, "history"))
    latest = os.path.join(branch_dir, "latest")
    if os.path.exists(latest):
        shutil.rmtree(latest)
    shutil.copytree(report, latest)


def create_indexes():
    print("Create index.html")
    __index_folder(public)
    __index_folder(branch_dir)


def main():
    clear_old_branches()
    prepare_directory()
    clear_old_reports()

    clear_secrets()
    create_allure()

    copy_folders()
    create_indexes()


if __name__ == "__main__":
   main()
