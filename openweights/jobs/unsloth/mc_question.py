from typing import List, Dict, Union
from dataclasses import dataclass
from enum import Enum
import random
import hashlib
from collections import defaultdict

from datasets import Dataset
import numpy as np

from logprobs import get_logprobs


@dataclass
class Choice:
    text: str
    is_correct: bool


class Question:
    def __init__(
        self, question: str,
        choices: List[Choice],
        id: str | None = None, 
        choice_template=None,
        question_template=None,
        answer_template=None,
        context=[]
    ):
        self.question = question
        self.choices = choices
        self.id = id or hashlib.sha256(question.encode()).hexdigest()
        self.choice_template = choice_template
        self.question_template = question_template
        self.answer_template = answer_template
        self.context = context
    
    def prepare(
        self,
        choice_template='{choice_char}: {choice_text}',
        question_template='{question_text}\n{choices_text}',
        answer_template=[{
            'type': 'text',
            'text': '{choice_char}',
            'logprobs': True,
        }],
        context=[],
        only_correct=False
    ):
        choice_template = self.choice_template or choice_template
        question_template = self.question_template or question_template
        answer_template = self.answer_template or answer_template
        context = self.context or context

        choices_text = '\n'.join([
            choice_template.format(choice_char=chr(65 + i), choice_text=choice.text)
            for i, choice in enumerate(self.choices)
        ])
        question_text = question_template.format(question_text=self.question, choices_text=choices_text)
        batch = []

        def apply_to_content_block(i, choice_char, choice_text):
            text = i['text'].format(choice_char=choice_char, choice_text=choice_text)
            return dict(i, text=text)

        for i, choice in enumerate(self.choices):
            if only_correct and not choice.is_correct:
                continue
            batch.append(dict(id=self.id, is_correct=choice.is_correct, messages=context + [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': question_text,
                            'logprobs': False
                        }
                    ]
                },
                {
                    'role': 'assistant',
                    'content': [
                        apply_to_content_block(block, choice_char=chr(65 + i), choice_text=choice.text)
                        for block in answer_template
                    ]
                }
            ]))
        return batch



class MultipleChoiceEval:
    def __init__(self, questions, choice_template: str, question_template: str, answer_template: List[Dict[str, Union[str, bool]]], context=[], randomize=True):
        self.questions : List[Question] = questions
        self.choice_template = choice_template
        self.question_template = question_template
        self.answer_template = answer_template
        self.context = context
        if randomize:
            self.randomize()
        self.ds = self.as_dataset()
    
    def randomize(self):
        """Randomize the order of choices"""
        for question in self.questions:
            random.shuffle(question.choices)
    
    def as_messages(self, only_correct=False) -> List[Dict]:
        messages = []
        for question in self.questions:
            messages.extend(question.prepare(self.choice_template, self.question_template, self.answer_template, self.context, only_correct))
        return messages
    
    def as_fewshot_context(self):
        conversations = self.as_messages(only_correct=True)
        messages = []
        for conversation in conversations:
            for message in conversation['messages']:
                messages.append(dict(role=message['role'], content=[{'text': message['content'][0]['text'], 'logprobs': False}]))
        return messages

    def as_dataset(self):
        messages = self.as_messages()
        return Dataset.from_dict({k: [dic[k] for dic in messages] for k in messages[0]})

    def get_logprobs(self, model, tokenizer, batch_size=4):
        logprobs = get_logprobs(model, tokenizer, self.ds, batch_size=batch_size)
        return logprobs

    def get_metrics(self, model, tokenizer, batch_size):
        logprob_results = self.get_logprobs(model, tokenizer, batch_size)

        questions = defaultdict(list)
        for example in logprob_results:
            questions[example['id']].append(example)
        
        # Calculate metrics
        correct_count = 0
        total_count = 0
        
        question_results = []
        
        for question_id, examples in questions.items():
            # Get the total logprob for each choice
            choice_scores = []
            for example in examples:
                # Access the logprobs from the last message (assistant's response)
                total_logprob = sum( # over messages
                    sum( # over blocks
                        [sum( # over tokens
                            block['logprobs'])
                        for block in message['content'] if block['logprobs'] is not False])
                    for message in example['messages']
                )
                choice_scores.append({
                    'is_correct': example['is_correct'],
                    'logprob': total_logprob
                })
                if example['is_correct']:
                    logp_correct = total_logprob
            
            # Find the choice with the highest logprob
            max_logprob_idx = np.argmax([choice['logprob'] for choice in choice_scores])
            predicted_correct = choice_scores[max_logprob_idx]['is_correct']
            
            # Update metrics
            if predicted_correct:
                correct_count += 1
            total_count += 1
            
            # Store results for this question
            question_results.append({
                'id': question_id,
                'correct': predicted_correct,
                'logp_correct': logp_correct,
                'choices': choice_scores
            })
        
        # Calculate accuracy
        accuracy = correct_count / total_count if total_count > 0 else 0
        
        return {
            'accuracy': accuracy,
            'correct_count': correct_count,
            'total_count': total_count,
            'question_results': question_results
        }


class MultipleChoiceEvalABC(MultipleChoiceEval):
    def __init__(
        self,
        questions,
        choice_template='{choice_char}: {choice_text}',
        question_template='{question_text}\n{choices_text}',
        answer_template=[{
            'type': 'text',
            'text': '{choice_char}',
            'logprobs': True,
        }],
        context=[]
    ):
        super().__init__(questions, choice_template, question_template, answer_template, context)


class MultipleChoiceEvalFreeform(MultipleChoiceEval):
    def __init__(
        self,
        questions,
        choice_template='{choice_text}',
        question_template='{question_text}',
        answer_template=[{
            'type': 'text',
            'text': '{choice_text}',
            'logprobs': True,
        }],
        context=[]
    ):
        super().__init__(questions, choice_template, question_template, answer_template, context)
