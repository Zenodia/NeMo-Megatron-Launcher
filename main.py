import copy
import math
import subprocess
import sys

import hydra
import omegaconf

from bignlp.bignlp_utils import convert_to_cli, fake_submit
from bignlp.conversion_scripts import convert
from bignlp.eval_scripts import evaluate_gpt, evaluate_prompt_gpt, evaluate_t5
from bignlp.export_scripts import export
from bignlp.finetune_scripts import finetune
from bignlp.prompt_learn_scripts import prompt_learn
from bignlp.train_scripts import train

omegaconf.OmegaConf.register_new_resolver("multiply", lambda x, y: x * y, replace=True)
omegaconf.OmegaConf.register_new_resolver("divide_ceil", lambda x, y: int(math.ceil(x / y)), replace=True)
omegaconf.OmegaConf.register_new_resolver("divide_floor", lambda x, y: int(math.floor(x / y)), replace=True)


@hydra.main(config_path="conf", config_name="config")
def main(cfg):
    hydra_args = convert_to_cli(cfg)

    if cfg.get("debug"):
        subprocess.check_output = fake_submit

    # Read config
    run_data_preparation = cfg.get("run_data_preparation")
    run_training = cfg.get("run_training")
    run_conversion = cfg.get("run_conversion")
    run_finetuning = cfg.get("run_finetuning")
    run_prompt_learning = cfg.get("run_prompt_learning")
    run_evaluation = cfg.get("run_evaluation")
    run_export = cfg.get("run_export")

    # TODO: build a mapping from dataset name to modules
    data_config = cfg.get("data_config")
    if "pile" in data_config:
        from bignlp.data_preparation import data_preparation_pile as data_preparation
    elif "mc4" in data_config:
        from bignlp.data_preparation import data_preparation_mc4 as data_preparation
    elif "custom" in data_config:
        from bignlp.data_preparation import data_preparation_custom as data_preparation
    else:
        raise ValueError(f"Unrecognized dataset in data config `{data_config}`.")

    cfg_copy = copy.deepcopy(cfg)
    dependency = None
    if run_data_preparation:
        dependency = data_preparation.run_data_preparation(cfg, hydra_args=hydra_args, dependency=dependency)
    else:
        cfg_copy._content.pop("data_preparation", None)

    if run_training:
        dependency = train.run_training(cfg, hydra_args=hydra_args, dependency=dependency)
    else:
        cfg_copy._content.pop("training", None)

    if run_conversion:
        dependency = convert.convert_ckpt(cfg, hydra_args=hydra_args, dependency=dependency)
    else:
        cfg_copy._content.pop("conversion", None)

    if run_finetuning:
        dependency = finetune.run_finetuning(cfg, hydra_args=hydra_args, dependency=dependency)
    else:
        cfg_copy._content.pop("finetuning", None)

    if run_prompt_learning:
        dependency = prompt_learn.run_prompt_learning(cfg, hydra_args=hydra_args, dependency=dependency)
    else:
        cfg_copy._content.pop("prompt_learning", None)

    # TODO: merge evaluation harness
    if run_evaluation:
        if "prompt_gpt3" in cfg.get("evaluation_config"):
            dependency = evaluate_prompt_gpt.run_evaluation(cfg, dependency=dependency)
        elif "gpt3" in cfg.get("evaluation_config"):
            dependency = evaluate_gpt.run_evaluation(cfg, dependency=dependency)
        elif "t5" in cfg.get("evaluation_config"):
            dependency = evaluate_t5.run_evaluation(cfg, hydra_args=hydra_args, dependency=dependency)
        else:
            raise ValueError(f"Unrecognized model in evaluation config `{cfg.evaluation_config}`.")
    else:
        cfg_copy._content.pop("evaluation", None)

    if run_export:
        dependency_export = export.run_export(cfg, dependency=dependency)
        # dependency_accuracy = export.run_accuracy(cfg, dependency=dependency_export)
        # dependency_performance = export.run_performance(cfg, dependency=dependency_export)
        dependency = dependency_export

    # print(omegaconf.OmegaConf.to_yaml(cfg_copy))


if __name__ == "__main__":
    main()
