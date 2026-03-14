from data_tools.schema import FileLoader, Result, CanonicalPath, FileType, File
import pytest


@pytest.fixture
def canonical_path_elements():
    event = "event"
    origin = "origin"
    source = "source"
    name = "name"

    return event, origin, source, name


@pytest.fixture
def file(canonical_path_elements):
    event, origin, source, name = canonical_path_elements
    data = {
        "some_data": 10,
        "another_field": 11
    }

    file_type = FileType.Any
    canonical_path = CanonicalPath(origin=origin, event=event, source=source, name=name)
    metadata = {"test": True}
    description = "This is a fake File, if you didn't already know. Oops."

    return data, file_type, metadata, description, canonical_path

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
