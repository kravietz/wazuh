# Copyright (C) 2015-2020, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is a free software; you can redistribute it and/or modify it under the terms of GPLv2

from datetime import datetime, date
from unittest.mock import patch, ANY

import pytest
from connexion import ProblemException

from api import util
from api.api_exception import APIException, APIError
from wazuh.core.exception import WazuhException, WazuhError


class TestClass():
    def __init__(self, origin=None):
        self.swagger_types = {
            'api_response': 'test_api_response',
            'data': str
        }
        self.attribute_map = {
            'api_response': 'api_response',
            'data': 'data'
        }
        self.__args__ = ['arg0', 'arg1', 'arg2']
        self.__origin__ = origin


@pytest.mark.parametrize('item, is_transformed', [
    (date.today(), False),
    (datetime.today(), True)
])
def test_serialize(item, is_transformed):
    """Assert serialize() function transform datetime as expected

    Parameters
    ----------
    item : date
        Date object to be transformed
    is_transformed : bool
        Whether if the returned object should remain the same
    """
    result = util.serialize(item)

    if is_transformed:
        assert result != item
    else:
        assert result == item


@pytest.mark.parametrize('item, klass', [
    ('test', str),
    ('2020-06-24 17:02:53.034374', datetime)
])
def test_deserialize_primitive(item, klass):
    """Check that _deserialize_primitive function returns expected object"""
    result = util._deserialize_primitive(item, klass)
    assert result == item


@pytest.mark.parametrize('item', [
    'test', True, {'key': 'value'}
])
def test_deserialize_object(item):
    """Check that _deserialize_object function works as expected"""
    result = util._deserialize_object(item)
    assert result == item


def test_deserialize_date():
    """Check that _deserialize_date function transforms string into date"""
    result = util.deserialize_date('2020-06-24')
    assert isinstance(result, date)


@patch('dateutil.parser.parse', side_effect=ImportError)
def test_deserialize_date_ko(mock_import):
    """Check that _deserialize_date function correctly handles expected exceptions"""
    result = util.deserialize_date('2020-06-24')
    assert not isinstance(result, date)


def test_deserialize_datetime():
    """Check that _deserialize_datetime function transforms string into datetime"""
    result = util.deserialize_datetime('2020-06-24 17:02:53.034374')
    assert isinstance(result, datetime)


@patch('dateutil.parser.parse', side_effect=ImportError)
def test_deserialize_datetime_ko(mock_import):
    """Check that _deserialize_datetime function correctly handles expected exceptions"""
    result = util.deserialize_datetime('2020-06-24 17:02:53.034374')
    assert not isinstance(result, date)


def test_deserialize_model():
    """Check that _deserialize_model function transforms item into desired object"""
    test = {'data': 'test'}
    result = util.deserialize_model(test, TestClass)

    assert result.data == 'test'
    assert isinstance(result, TestClass)
    assert isinstance(result.attribute_map, dict)
    assert isinstance(result.swagger_types, dict)


def test_deserialize_list():
    """Check that _deserialize_list function transforms list of items into list of desired objects"""
    test = ['test1', 'test2']
    result = util._deserialize_list(test, TestClass)
    assert all(isinstance(x, TestClass) for x in result)


def test_deserialize_dict():
    """Check that _deserialize_dict function transforms dict of items into dict of desired objects"""
    test = {'key1': 'value', 'key2': 'value', 'key3': 'value'}
    result = util._deserialize_dict(test, TestClass)
    assert all(isinstance(x, TestClass) for x in result.values())


@patch('api.util._deserialize_primitive')
@patch('api.util._deserialize_object')
@patch('api.util.deserialize_date')
@patch('api.util.deserialize_datetime')
@patch('api.util._deserialize_list')
@patch('api.util._deserialize_dict')
@patch('api.util.deserialize_model')
def test_deserialize(mock_model, mock_dict, mock_list, mock_datetime, mock_date, mock_object, mock_primitive):
    """Check that _deserialize calls the expected function depending on the class"""
    assert util._deserialize(None, None) is None

    util._deserialize(30, int)
    mock_primitive.assert_called_once_with(30, int)

    test_object = TestClass(origin=list)
    util._deserialize(test_object, object)
    mock_object.assert_called_once_with(test_object)

    util._deserialize('test_date', date)
    mock_date.assert_called_once_with('test_date')

    util._deserialize('test_date', datetime)
    mock_datetime.assert_called_once_with('test_date')

    util._deserialize([0, 1, 2], test_object)
    mock_list.assert_called_once_with([0, 1, 2], 'arg0')

    test_object = TestClass(origin=dict)
    util._deserialize({'test_key': 'test_value'}, test_object)
    mock_dict.assert_called_once_with({'test_key': 'test_value'}, 'arg1')

    util._deserialize(['test'], list)
    mock_model.assert_called_once_with(['test'], list)


def test_remove_nones_to_dict():
    """Check that remove_nones_to_dict removes key:value when value is None"""
    result = util.remove_nones_to_dict({'key1': 'value1', 'key2': None, 'key3': 'value3'})
    assert 'key2' not in result.keys()


@pytest.mark.parametrize('param, param_type, expected_result', [
    (None, 'search', None),
    (None, 'sort', None),
    (None, 'random', None),
    ('ubuntu', 'search', {'value': 'ubuntu', 'negation': False}),
    ('-ubuntu', 'search', {'value': 'ubuntu', 'negation': True}),
    ('field1', 'sort', {'fields': ['field1'], 'order': 'asc'}),
    ('field1,field2', 'sort', {'fields': ['field1', 'field2'], 'order': 'asc'}),
    ('-field1,field2', 'sort', {'fields': ['field1', 'field2'], 'order': 'desc'}),
    ('random', 'random', 'random')
])
def test_parse_api_param(param, param_type, expected_result):
    """Check that parse_api_param returns the expected result"""
    assert util.parse_api_param(param, param_type) == expected_result


@patch('os.path.relpath')
def test_to_relative_path(mock_real_path):
    """Check that to_relative_path calls expected function with given params"""
    util.to_relative_path('api/conf/api.yaml')
    mock_real_path.assert_called_once_with('api/conf/api.yaml', ANY)


@pytest.mark.parametrize('exception_type, code, extra_fields, returned_code, returned_exception', [
    (ValueError, 100, None, ValueError(100), ValueError),
    (WazuhError, 1000, ['remediation', 'code', 'dapi_errors'], 400, ProblemException),
    (WazuhException, 3004, ['remediation', 'code', 'dapi_errors'], 500, ProblemException),
    (APIException, 2000, ['code'], 500, ProblemException),
    (APIError, 2000, ['code'], 400, ProblemException),
])
def test_create_problem(exception_type, code, extra_fields, returned_code, returned_exception):
    """Check that _create_problem returns exception with expected data"""
    with pytest.raises(returned_exception) as exc_info:
        util._create_problem(exception_type(code))

    if returned_exception == ProblemException:
        assert exc_info.value.status == returned_code
    if extra_fields:
        assert all(x in exc_info.value.ext.keys() for x in extra_fields)
        assert None not in exc_info.value.ext.values()


@pytest.mark.parametrize('obj', [
    WazuhError(1000), ['value0', 'value1']
])
@patch('api.util._create_problem')
def test_raise_if_exc(mock_create_problem, obj):
    """Check that raise_if_exc calls _create_problem when an exception is given"""
    result = util.raise_if_exc(obj)

    if isinstance(obj, Exception):
        mock_create_problem.assert_called_once_with(obj)
    else:
        assert result == obj
