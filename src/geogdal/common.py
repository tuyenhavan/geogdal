import os


def list_files(path, ext=None):
    """
    List all files in a directory with a specific extension.
    args:
        path (str): Directory path to search for files.
        ext (str, optional): File extension to filter by. Defaults to None.
    returns:
        list: Sorted list of filenames with the specified extension.
    """
    flist = []

    for dir, _, files in os.walk(path):
        for file in files:
            if file.endswith(ext):
                flist.append(file)
            else:
                if ext is None:
                    flist.append(file)
    return sorted(flist)
