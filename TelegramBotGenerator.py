import importlib

#  generator obj
generator = None


# import generator
def init(script="GeneratorLlamaCpp", model_path="", n_ctx=4096):
    generator_class = getattr(importlib.import_module("generators." + script), "Generator")
    global generator
    generator = generator_class(model_path, n_ctx)


def get_answer(
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer: str,
        turn_template='',
        **kwargs):
    # Preparing, add stopping_strings
    answer = default_answer

    print("stopping_strings =", stopping_strings)
    print(prompt, end="")
    try:
        answer = generator.get_answer(prompt, generation_params, eos_token, stopping_strings, default_answer,
                                      turn_template)
    except Exception as e:
        print("generation error:", e)
    print(answer)
    return answer


def tokens_count(text: str):
    return generator.tokens_count(text)


def get_model_list():
    return generator.get_model_list()


def load_model(model_file: str):
    return generator.load_model(model_file)
