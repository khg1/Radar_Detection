# Copyright 2024. All Rights Reserved.
#
# This source code is provided solely for runtime interpretation by Python.
# 
# This python file is used explicitly to meet the project requirements provided
# in ENDG 511 at the University of Calgary.

from __future__ import annotations
from typing import TYPE_CHECKING, Union, Tuple
if TYPE_CHECKING:
    from rodnet.models import (
        RODNetCDC, 
        RODNetHG, 
        RODNetHGwI, 
        RODNetCDCDCN, 
        RODNetHGDCN, 
        RODNetHGwIDCN
    )

from rodnet.utils.load_configs import (
    load_configs_from_file, 
    parse_cfgs, 
    update_config_dict
)
from prune import (
    global_unstructured_pruning,
    multi_parameter_unstructured_pruning,
    print_sparsity
)
from quantize import (
    static_quantization,
    dynamic_quantization
)
from cruw import CRUW
import argparse
import torch
import os

def print_size_of_model(
        rodnet: Union[
            RODNetCDC, 
            RODNetHG, 
            RODNetHGwI, 
            RODNetCDCDCN, 
            RODNetHGDCN, 
            RODNetHGwIDCN]):
    """
    Print the size of the model in KB.

    Parameters
    ----------
        rodnet: Type[nn.Module]
            The loaded pytorch model to check for model size.
    """
    torch.save(rodnet.state_dict(), "temp.p")
    print('Size (KB):', os.path.getsize("temp.p")/1e3)
    os.remove('temp.p')

def print_parameters(
        rodnet: Union[
            RODNetCDC, 
            RODNetHG, 
            RODNetHGwI, 
            RODNetCDCDCN, 
            RODNetHGDCN, 
            RODNetHGwIDCN]) -> Tuple[int, int]:
    """
    Prints the number of parameters at the encoder and decoder portions of
    the model.

    Parameters
    ----------
        rodnet: Type[nn.Module]
            The loaded pytorch model to check for the number of parameters.

    Returns
    -------
        encoder_parameters: int
            The number of parameters of the encoder.

        decoder_parameters: int
            The number of parameters of the decoder.
    """
    encoder_parameters = sum(p.numel() for p in rodnet.cdc.encoder.parameters())
    decoder_parameters = sum(p.numel() for p in rodnet.cdc.decoder.parameters())
    print(f"{encoder_parameters=}, {decoder_parameters=}")
    return encoder_parameters, decoder_parameters

def print_parameter_type(
        rodnet: Union[
            RODNetCDC, 
            RODNetHG, 
            RODNetHGwI, 
            RODNetCDCDCN, 
            RODNetHGDCN, 
            RODNetHGwIDCN]):
    """
    Prints the type of each model parameter, this is to check the 
    datatype to confirm wether or not the model changed after
    quantization.

    Parameters
    ----------
        rodnet: Type[nn.Module]
            The loaded pytorch model to check for parameter type.
    """
    for n, p in rodnet.named_parameters():
        print(n, ": ", p.dtype)

def check_path(file_path: str) -> str:
    """
    Checks if the path exists or not.

    Parameters
    ----------
        file_path: str
            This is the path to check.

    Returns
    -------
        file_path: str
            If this path exists, then it is returned.
    """
    if file_path is not None and os.path.exists(file_path):
        return file_path
    else:
        raise ValueError(f"The following path does not exist: {file_path}")

def load_model(checkpoint_path: str) -> dict:
    """
    Loads a PKL model file path.

    Parameters
    ----------
        checkpoint_path: str
            This is the PKL path to load torch.

    Returns
    -------
        checkpoint: dict
            This is a loaded pkl file stored as a dictionary.
    """
    return torch.load(checkpoint_path)

def build_model(
        config_dict: dict, 
        dataset: CRUW, 
        use_noise_channel: bool, 
        checkpoint: dict
    ):
    """
    Builds the model architecture based on configurations.

    Parameters
    ----------
        config_dict: dict
            The model configurations
        
        dataset: CRUW
            Dataset configurations used to train the model.

        use_noise_channel: bool
            Specification to use noise channel from the command line.

        checkpoint: dict
            The loaded pkl model file from training.

    Returns
    -------
        rodnet: Type[nn.Module]
            This is a specific RodNet architecture depending on the model
            configurations.
    """
    radar_configs = dataset.sensor_cfg.radar_cfg
    n_class = dataset.object_cfg.n_class

    if use_noise_channel:
        n_class_test = n_class + 1
    else:
        n_class_test = n_class

    model_cfg = config_dict['model_cfg']
    if 'stacked_num' in model_cfg:
        stacked_num = model_cfg['stacked_num']
    else:
        stacked_num = None

    if model_cfg['type'] == 'CDC':
        from rodnet.models import RODNetCDC
        rodnet = RODNetCDC(in_channels=2, n_class=n_class_test).cuda()
    elif model_cfg['type'] == 'HG':
        from rodnet.models import RODNetHG
        rodnet = RODNetHG(
            in_channels=2, 
            n_class=n_class_test, 
            stacked_num=stacked_num).cuda()
    elif model_cfg['type'] == 'HGwI':
        from rodnet.models import RODNetHGwI
        rodnet = RODNetHGwI(
            in_channels=2, 
            n_class=n_class_test, 
            stacked_num=stacked_num).cuda()
    elif model_cfg['type'] == 'CDCv2':
        from rodnet.models import RODNetCDCDCN
        in_chirps = len(radar_configs['chirp_ids'])
        rodnet = RODNetCDCDCN(
            in_channels=in_chirps, 
            n_class=n_class_test,            
            mnet_cfg=config_dict['model_cfg']['mnet_cfg'],
            dcn=config_dict['model_cfg']['dcn']).cuda()
    elif model_cfg['type'] == 'HGv2':
        from rodnet.models import RODNetHGDCN
        in_chirps = len(radar_configs['chirp_ids'])
        rodnet = RODNetHGDCN(
            in_channels=in_chirps, 
            n_class=n_class_test, 
            stacked_num=stacked_num,
            mnet_cfg=config_dict['model_cfg']['mnet_cfg'],
            dcn=config_dict['model_cfg']['dcn']).cuda()
    elif model_cfg['type'] == 'HGwIv2':
        from rodnet.models import RODNetHGwIDCN
        in_chirps = len(radar_configs['chirp_ids'])
        rodnet = RODNetHGwIDCN(
            in_channels=in_chirps, 
            n_class=n_class_test, 
            stacked_num=stacked_num,
            mnet_cfg=config_dict['model_cfg']['mnet_cfg'],
            dcn=config_dict['model_cfg']['dcn']).cuda()
    else:
        raise NotImplementedError(
            f"The following model type is not supported: {model_cfg['type']}")
    
    if 'optimizer_state_dict' in checkpoint:
        rodnet.load_state_dict(checkpoint['model_state_dict'])
    else:
        rodnet.load_state_dict(checkpoint)
    # Set model to eval mode.
    rodnet.eval()
    return rodnet

def main():
    """
    Main program starting point.
    """
    parser = argparse.ArgumentParser(
        description='Prune RODNet.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--config', 
        type=str, 
        help='choose rodnet model configurations'
    )
    parser.add_argument(
        '--sensor_config', 
        type=str, 
        default='sensor_config_rod2021'
    )
    parser.add_argument(
        '--checkpoint', 
        type=str, 
        help='path to the saved trained model'
    )
    parser.add_argument(
        '--res_dir', 
        type=str, 
        default='./results/', 
        help='directory to save testing results'
    )
    parser.add_argument(
        '--use_noise_channel', 
        action="store_true", 
        help="use noise channel or not"
    )
    parser.add_argument(
        '--pruning_type',
        type=str,
        choices=["global", "local"],
        help="The type of unstructured pruning to perform: local or global."
    )
    parser.add_argument(
        '--prune_sparsity',
        type=float,
        default=0.2,
        help="The pruning sparsity to set for pruning the weights."
    )
    parser.add_argument(
        '--quantization_type',
        type=str,
        choices=["static", "dynamic"],
        help="The type of post-training quantization to perform."
    )
    parser.add_argument(
        '--half',
        action="store_true",
        help="Perform half precision quantization on the model."
    )
    parser = parse_cfgs(parser)
    args = parser.parse_args()

    config_dict = load_configs_from_file(args.config)
    config_dict = update_config_dict(config_dict, args)  # Update configs by args.

    dataset = CRUW(
        data_root=config_dict['dataset_cfg']['base_root'], 
        sensor_config_name=args.sensor_config)

    """
    # The following code is for dataset testing purposes.
    range_grid = dataset.range_grid
    angle_grid = dataset.angle_grid

    dataset_configs = config_dict['dataset_cfg']
    train_configs = config_dict['train_cfg']
    test_configs = config_dict['test_cfg']
    win_size = train_configs['win_size']
    """
    
    checkpoint_path = check_path(args.checkpoint)
    checkpoint = load_model(checkpoint_path)
    rodnet = build_model(config_dict, dataset, args.use_noise_channel, checkpoint)
    
    encoder_parameters, decoder_parameters = print_parameters(rodnet)
    print(f"Total Base parameters = {encoder_parameters + decoder_parameters}")
    print_size_of_model(rodnet)
    print_parameter_type(rodnet)

    """Pruning Methods"""
    print("\n...Performing Pruning...")
    if isinstance(args.pruning_type, str):
        if args.pruning_type.lower() == "global":
            rodnet = global_unstructured_pruning(
                rodnet, amount=args.prune_sparsity)
        elif args.pruning_type.lower() == "local":
            rodnet = multi_parameter_unstructured_pruning(
                rodnet, args.prune_sparsity, args.prune_sparsity)
        else:
            raise ValueError(f"Unrecognized pruning type: {args.pruning_type}")
        print_sparsity(rodnet)
        encoder_parameters, decoder_parameters = print_parameters(rodnet)
        print(f"Total Pruned parameters = {encoder_parameters + decoder_parameters}")
        print_size_of_model(rodnet)

    """Precision Decrease"""
    if args.half:
        print("\n...Performing Quantization...")
        rodnet = rodnet.half()
        print_size_of_model(rodnet)

    """Quantization Methods"""
    if isinstance(args.quantization_type, str):
        print("\n...Performing Quantization...")
        if args.quantization_type.lower() == "static":
            quantized_model = static_quantization(rodnet, config_dict)
        elif args.quantization_type.lower() == "dynamic":
            quantized_model = dynamic_quantization(rodnet)
        else:
            raise ValueError(f"Unrecognized quantization type: {args.quantization_type}")
        
        print_parameter_type(quantized_model)
        print_size_of_model(quantized_model)
        print(quantized_model)

if __name__ == '__main__':
    main()