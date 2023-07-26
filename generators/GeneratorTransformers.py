from transformers import AutoTokenizer
import transformers
import torch
import os


class Generator:
    n_ctx = 8196
    seed = 0
    n_gpu_layers = 0

    def __init__(self, telegram_llm_model_path_file, n_ctx, seed, n_gpu_layers):
        model = "pranavpsv/gpt2-genre-story-generator"
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=model,
            device_map="auto",
        )

    def get_answer(self,
            prompt,
            generation_params,
            eos_token,
            stopping_strings,
            default_answer,
            turn_template='',
            **kwargs):
        if "max_tokens" in generation_params:
            max_tokens = generation_params["max_tokens"]
        if "temperature" in generation_params:
            temperature = generation_params["temperature"]
        top_k = 10
        if "top_k" in generation_params:
            top_k = generation_params["top_k"]

        sequences = self.pipeline(
            prompt,
            do_sample=True,
            top_k=top_k,
            num_return_sequences=1,
            eos_token_id=self.tokenizer.eos_token_id,
            max_length=200,
        )
        answer = ""
        for seq in sequences:
            answer += seq['generated_text']
            print(f"Result: {seq['generated_text']}")
        return answer


    def tokens_count(self, text: str):
        return 0


    def get_model_list(self):
        pass


    def load_model(self, model_file: str):
        pass
