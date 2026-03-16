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
                flist.append(os.path.join(dir, file))
            else:
                if ext is None:
                    flist.append(os.path.join(dir, file))
    return sorted(flist)


def delete_files(path):
    """
    Delete all files in a directory.

    Args:
        path (str): The path to the directory containing files to be deleted.
    Returns:
        None
    """
    if not os.path.isdir(path):
        raise ValueError(f"The provided path '{path}' is not a valid directory.")
    for root, _, files in os.walk(path):
        for file in files:
            os.remove(os.path.join(root, file))
