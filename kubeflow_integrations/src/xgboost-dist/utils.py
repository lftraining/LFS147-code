# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import joblib
import xgboost as xgb
import os
import tempfile
import oss2
import json
import pandas as pd

from sklearn import datasets

logger = logging.getLogger(__name__)


def extract_xgbooost_cluster_env():
    """
    Extract the cluster env from pod
    :return: the related cluster env to build rabit
    """

    logger.info("starting to extract system env")

    master_addr = os.environ.get("MASTER_ADDR", "{}")
    master_port = int(os.environ.get("MASTER_PORT", "{}"))
    rank = int(os.environ.get("RANK", "{}"))
    world_size = int(os.environ.get("WORLD_SIZE", "{}"))

    logger.info("extract the Rabit env from cluster :"
                " %s, port: %d, rank: %d, word_size: %d ",
                master_addr, master_port, rank, world_size)

    return master_addr, master_port, rank, world_size


def read_train_data(rank, num_workers, path):
    """
    Read file based on the rank of worker.
    We use the sklearn.iris data for demonstration
    You can extend this to read distributed data source like HDFS, HIVE etc
    :param rank: the id of each worker
    :param num_workers: total number of workers in this cluster
    :param path: the input file name or the place to read the data
    :return: XGBoost Dmatrix
    """
    iris = datasets.load_iris()
    x = iris.data
    y = iris.target

    start, end = get_range_data(len(x), rank, num_workers)
    x = x[start:end, :]
    y = y[start:end]

    x = pd.DataFrame(x)
    y = pd.DataFrame(y)
    dtrain = xgb.DMatrix(data=x, label=y)

    logging.info("Read data from IRIS data source with range from %d to %d",
                 start, end)

    return dtrain


def read_predict_data(rank, num_workers, path):
    """
    Read file based on the rank of worker.
    We use the sklearn.iris data for demonstration
    You can extend this to read distributed data source like HDFS, HIVE etc
    :param rank: the id of each worker
    :param num_workers: total number of workers in this cluster
    :param path: the input file name or the place to read the data
    :return: XGBoost Dmatrix, and real value
    """
    iris = datasets.load_iris()
    x = iris.data
    y = iris.target

    start, end = get_range_data(len(x), rank, num_workers)
    x = x[start:end, :]
    y = y[start:end]
    x = pd.DataFrame(x)
    y = pd.DataFrame(y)

    logging.info("Read data from IRIS datasource with range from %d to %d",
                 start, end)

    predict = xgb.DMatrix(x, label=y)

    return predict, y


def get_range_data(num_row, rank, num_workers):
    """
    compute the data range based on the input data size and worker id
    :param num_row: total number of dataset
    :param rank: the worker id
    :param num_workers: total number of workers
    :return: begin and end range of input matrix
    """
    num_per_partition = int(num_row/num_workers)

    x_start = rank * num_per_partition
    x_end = (rank + 1) * num_per_partition

    if x_end > num_row:
        x_end = num_row

    return x_start, x_end


def dump_model(model, storage_type, model_path, args):
    """
    Dump the trained XGBoost model to a specified location.
    This function is optimized for handling XGBoost models using their native serialization method.
    
    :param model: the trained XGBoost model
    :param storage_type: model storage type ('local' or 'oss' for Object Storage Service)
    :param model_path: the local or remote path where the model will be stored
    :param args: additional configuration for model storage, including parameters for OSS
    :return: True if the dump process is successful
    """
    if model is None:
        raise Exception("Fail to get the XGBoost train model")

    if storage_type == "local":
        # Use XGBoost's native serialization for saving the model
        model.save_model(model_path)
        logging.info("Dumped XGBoost model into local place %s", model_path)

    elif storage_type == "oss":
        # Temporary local save before uploading to OSS
        # Generate a temporary local filename
        temp_model_path = "temp_xgboost_model.json"
        model.save_model(temp_model_path)

        # Configure and execute the upload to OSS
        oss_param = parse_parameters(args.oss_param, ",", ":")
        if oss_param is None:
            raise Exception("Please configure OSS parameters to store the model")
        oss_param['path'] = model_path
        dump_model_to_oss(oss_param, temp_model_path)
        logging.info("Dumped XGBoost model into OSS place %s", model_path)

        # Clean up the temporary local file
        os.remove(temp_model_path)

    return True

def read_model(type, model_path, args):
    """
    read model from physical storage
    :param type: oss or local
    :param model_path: place to store the model
    :param args: configuration to read model
    :return: XGBoost model
    """

    if type == "local":
        model = joblib.load(model_path)
        logging.info("Read model from local place %s", model_path)

    elif type == "oss":
        oss_param = parse_parameters(args.oss_param, ",", ":")
        if oss_param is None:
            raise Exception("Please config oss to read model")
            return False

        oss_param['path'] = args.model_path        

        model = read_model_from_oss(oss_param)
        logging.info("read model from oss place %s", model_path)

    return model


def dump_model_to_oss(oss_parameters, booster):
    """
    dump the model to remote OSS disk
    :param oss_parameters: oss configuration
    :param booster: XGBoost model
    :return: True if stored procedure is success
    """
    """export model into oss"""
    model_fname = os.path.join(tempfile.mkdtemp(), 'model')
    text_model_fname = os.path.join(tempfile.mkdtemp(), 'model.text')
    feature_importance = os.path.join(tempfile.mkdtemp(),
                                      'feature_importance.json')

    oss_path = oss_parameters['path']
    logger.info('---- export model ----')
    booster.save_model(model_fname)
    booster.dump_model(text_model_fname)  # format output model
    fscore_dict = booster.get_fscore()
    with open(feature_importance, 'w') as file:
        file.write(json.dumps(fscore_dict))
        logger.info('---- chief dump model successfully!')

    if os.path.exists(model_fname):
        logger.info('---- Upload Model start...')

        while oss_path[-1] == '/':
            oss_path = oss_path[:-1]

        upload_oss(oss_parameters, model_fname, oss_path)
        aux_path = oss_path + '_dir/'
        upload_oss(oss_parameters, model_fname, aux_path)
        upload_oss(oss_parameters, text_model_fname, aux_path)
        upload_oss(oss_parameters, feature_importance, aux_path)
    else:
        raise Exception("fail to generate model")
        return False

    return True


def upload_oss(kw, local_file, oss_path):
    """
    help function to upload a model to oss
    :param kw: OSS parameter
    :param local_file: local place of model
    :param oss_path: remote place of OSS
    :return: True if the procedure is success
    """
    if oss_path[-1] == '/':
        oss_path = '%s%s' % (oss_path, os.path.basename(local_file))

    auth = oss2.Auth(kw['access_id'], kw['access_key'])
    bucket = kw['access_bucket']
    bkt = oss2.Bucket(auth=auth, endpoint=kw['endpoint'], bucket_name=bucket)

    try:
        bkt.put_object_from_file(key=oss_path, filename=local_file)
        logger.info("upload %s to %s successfully!" %
                    (os.path.abspath(local_file), oss_path))
    except Exception():
        raise ValueError('upload %s to %s failed' %
                         (os.path.abspath(local_file), oss_path))


def read_model_from_oss(kw):
    """
    helper function to read a model from oss
    :param kw: OSS parameter
    :return: XGBoost booster model
    """
    auth = oss2.Auth(kw['access_id'], kw['access_key'])
    bucket = kw['access_bucket']
    bkt = oss2.Bucket(auth=auth, endpoint=kw['endpoint'], bucket_name=bucket)
    oss_path = kw["path"]

    temp_model_fname = os.path.join(tempfile.mkdtemp(), 'local_model')
    try:
        bkt.get_object_to_file(key=oss_path, filename=temp_model_fname)
        logger.info("success to load model from oss %s", oss_path)
    except Exception as e:
        logging.error("fail to load model: " + e)
        raise Exception("fail to load model from oss %s", oss_path)

    bst = xgb.Booster({'nthread': 2})  # init model

    bst.load_model(temp_model_fname)

    return bst


def parse_parameters(input, splitter_between, splitter_in):
    """
    helper function parse the input parameter
    :param input: the string of configuration like key-value pairs
    :param splitter_between: the splitter between config for input string
    :param splitter_in: the splitter inside config for input string
    :return: key-value pair configuration
    """

    ky_pairs = input.split(splitter_between)

    confs = {}

    for kv in ky_pairs:
        conf = kv.split(splitter_in)
        key = conf[0].strip(" ")
        if key == "objective" or key == "endpoint":
            value = conf[1].strip("'") + ":" + conf[2].strip("'")       
        else:
            value = conf[1]

        confs[key] = value
    return confs

