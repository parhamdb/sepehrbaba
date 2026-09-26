import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('track_occluders', Path(__file__).parents[1]/'scripts/track_occluders.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PromptValidation(unittest.TestCase):
    def document(self):
        return {'objects': [{'id': 1, 'motion_review': 'Reviewed movement in source',
                             'prompts': [{'image': 'frame.jpg', 'points': [[.2, .4]], 'labels': [1]}]}]}

    def test_valid_reviewed_prompt(self):
        self.assertEqual(len(module.validate_prompts(self.document(), ['frame.jpg'])), 1)

    def test_missing_frame_rejected(self):
        with self.assertRaises(ValueError):
            module.validate_prompts(self.document(), ['different.jpg'])

    def test_unreviewed_object_rejected(self):
        data = self.document(); data['objects'][0]['motion_review'] = ''
        with self.assertRaises(ValueError):
            module.validate_prompts(data, ['frame.jpg'])

    def test_invalid_coordinates_rejected(self):
        for point in ([float('nan'), .5], [1.1, .5], [-.1, .5]):
            data = self.document(); data['objects'][0]['prompts'][0]['points'] = [point]
            with self.assertRaises(ValueError):
                module.validate_prompts(data, ['frame.jpg'])


if __name__ == '__main__':
    unittest.main()
