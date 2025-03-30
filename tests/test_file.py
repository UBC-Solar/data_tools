from data_tools.schema import CanonicalPath, FileType, File
import pytest
import pathlib
from pydantic import ValidationError


@pytest.fixture
def canonical_path_elements():
    event = "event"
    origin = "origin"
    source = "source"
    name = "name"

    return event, origin, source, name


def test_canonical_path(canonical_path_elements):
    event, origin, source, name = canonical_path_elements
    path_from_str = pathlib.Path(origin) / event / source / name

    canonical_path = CanonicalPath(origin=origin, event=event, source=source, name=name)

    assert canonical_path.to_string() == "origin/event/source/name"
    assert canonical_path.to_path() == path_from_str

    assert canonical_path.origin == origin
    assert canonical_path.source == source
    assert canonical_path.name == name
    assert canonical_path.event == event

    assert str(canonical_path) == canonical_path.to_string()
    assert repr(canonical_path) == canonical_path.to_string()

    assert canonical_path.unwrap() == [origin, event, source, name]
    assert CanonicalPath.unwrap_canonical_path(canonical_path.to_string()) == canonical_path.unwrap()


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


def test_file(file):
    data, file_type, metadata, description, canonical_path = file

    # Ensure successful creation
    file = File(
        data=data,
        file_type=file_type,
        canonical_path=canonical_path,
        metadata=metadata,
        description=description
    )

    assert file.data == data
    assert file.metadata == metadata
    assert file.description == description
    assert file.file_type == file_type
    assert file.canonical_path == canonical_path

    # Ensure that validation errors get raised for incorrect types

    with pytest.raises(ValidationError):
        File(
            data=data,
            file_type="NotAValidFileType",
            canonical_path=canonical_path,
            metadata=metadata,
            description=description
        )

    with pytest.raises(ValidationError):
        File(
            data=data,
            file_type=file_type,
            canonical_path="NotAValidPath",
            metadata=metadata,
            description=description
        )

    with pytest.raises(ValidationError):
        File(
            data=data,
            file_type=file_type,
            canonical_path=canonical_path,
            metadata="NotValidMetaData",
            description=description
        )

    with pytest.raises(ValidationError):
        File(
            data=data,
            file_type=file_type,
            canonical_path=canonical_path,
            metadata=metadata,
            description={"description": "This should raise an error."}
        )

