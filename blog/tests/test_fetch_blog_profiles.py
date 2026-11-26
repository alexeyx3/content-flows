import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scripts.fetch_blog_profiles import profile_records


def test_cms_relations_keep_exact_profile_name_and_only_public_identity():
    response = {'data': [{'author': {'id': 5, 'username': 'john.roe',
        'name': 'John Roe', 'email': 'private@example.com'},
        'editors': [{'id': 4, 'username': 'jane.doe', 'name': 'Jane Doe'}]}]}
    assert profile_records(response, {'john.roe': 5, 'jane.doe': 4}) == [
        {'id': 5, 'username': 'john.roe', 'name': 'John Roe'},
        {'id': 4, 'username': 'jane.doe', 'name': 'Jane Doe'}]


def test_missing_name_never_falls_back_to_username():
    with pytest.raises(ValueError, match='Missing CMS speaker'):
        profile_records({'data': [{'author': {'id': 5, 'username': 'john.roe'}}]},
                        {'john.roe': 5})


def test_conflicting_names_or_identity_are_rejected():
    with pytest.raises(ValueError, match='conflicting'):
        profile_records({'data': [{'author': {'id': 5, 'name': 'Mike'}},
                                 {'author': {'id': 5, 'name': 'Mikhail'}}]}, {'john.roe': 5})
    with pytest.raises(ValueError, match='ID/username'):
        profile_records({'data': [{'author': {'id': 5, 'username': 'wrong', 'name': 'Mike'}}]},
                        {'john.roe': 5})
