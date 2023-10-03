import time

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = True  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path, n_ctx=2048, seed=0, n_gpu_layers=0):
        self.model_path = "like"

    def get_answer(
        self,
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer,
        turn_template="",
        **kwargs,
    ):
        if self.model_path == "like":
            time.sleep(2)
            answer = "😀 " + prompt + " 👍"
        elif self.model_path == "dislike":
            time.sleep(2)
            answer = "🙁 " + prompt + " 👎"
        else:
            answer = "generator: model_path unknown"
        return answer

    def tokens_count(self, text: str):
        return len(text)

    def get_model_list(self):
        return ["like", "dislike"]

    def load_model(self, model_file: str):
        self.model_path = model_file

