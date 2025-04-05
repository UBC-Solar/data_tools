from data_tools.schema import FileLoader, File, Result
from tests.test_file import canonical_path_elements, file


def test_file_loader(file):
    data, file_type, metadata, description, canonical_path = file

    # Ensure successful creation
    file = File(
        data=data,
        file_type=file_type,
        canonical_path=canonical_path,
        metadata=metadata,
        description=description
    )

    # Fake query function that just returns the file wrapped in a result
    file_result = Result.Ok(file)
    query_func = lambda _: file_result

    file_loader = FileLoader(loader=query_func, canonical_path=canonical_path)

    assert file_loader.canonical_path == canonical_path
    assert file_loader() == file_result
