"""Tests for the mycroft skill's get_response variations."""

from os.path import dirname, join
from threading import Thread
import time
from unittest import TestCase, mock, skip

from lingua_franca import load_language

from ovos_workshop.skills.mycroft_skill import MycroftSkill
from ovos_bus_client import Message

from .mocks import base_config, AnyCallable


load_language("en-us")


def create_converse_responder(response, skill):
    """Create a function to inject a response into the converse method.

    The function waits for the converse method to be replaced by the
    _wait_response logic and afterwards injects the provided response.

    Args:
        response (str): Sentence to inject.
        skill (MycroftSkill): skill to monitor.
    """
    default_converse = skill.converse
    converse_return = None

    def wait_for_new_converse():
        """Wait until there is a new converse handler then send sentence.
        """
        nonlocal converse_return
        start_time = time.monotonic()
        while time.monotonic() < start_time + 5:
            if skill.converse != default_converse:
                skill.converse([response])
                break

            time.sleep(0.1)

    return wait_for_new_converse


@mock.patch('mycroft.configuration.Configuration')
def create_skill(mock_conf, lang='en-us'):
    cfg = base_config()
    cfg["lang"] = lang
    mock_conf.get.return_value = cfg
    bus = mock.Mock()
    skill = MycroftSkill(name='test_skill')
    skill.root_dir = join(dirname(__file__), 'test_skill')
    skill._startup(bus)
    return skill


@skip("TODO - update/fix me")
class TestMycroftSkillWaitResponse(TestCase):

    def test_wait(self):
        """Ensure that _wait_response() returns the response from converse."""
        skill = create_skill()

        expected_response = 'Yes I do, very much'

        converser = Thread(target=create_converse_responder(expected_response,
                                                            skill))
        converser.start()
        validator = mock.Mock()
        validator.return_value = True
        is_cancel = mock.Mock()
        is_cancel.return_value = False
        on_fail = mock.Mock()

        response = skill._wait_response(is_cancel, validator, on_fail, 1)
        self.assertEqual(response, expected_response)
        converser.join()

    def test_wait_cancel(self):
        """Test that a matching cancel function cancels the wait."""
        skill = create_skill()

        converser = Thread(target=create_converse_responder('cancel', skill))
        converser.start()
        validator = mock.Mock()
        validator.return_value = False
        on_fail = mock.Mock()

        def is_cancel(utterance):
            return utterance == 'cancel'

        response = skill._wait_response(is_cancel, validator, on_fail, 1, Message(""))
        self.assertEqual(response, None)
        converser.join()


@skip("TODO - update/fix me")
class TestMycroftSkillGetResponse(TestCase):
    def test_get_response(self):
        """Test response using a dialog file."""
        skill = create_skill()
        skill._wait_response = mock.Mock()
        skill.speak_dialog = mock.Mock()

        expected_response = 'ice creamr please'
        skill._wait_response.return_value = expected_response
        response = skill.get_response('what do you want')
        self.assertEqual(response, expected_response)
        self.assertTrue(skill.speak_dialog.called)

    def test_get_response_text(self):
        """Assert that text is used if no dialog exists."""
        skill = create_skill()
        skill._wait_response = mock.Mock()
        skill.speak_dialog = mock.Mock()

        expected_response = 'green'
        skill._wait_response.return_value = expected_response
        response = skill.get_response('tell me a color')
        self.assertEqual(response, expected_response)
        self.assertTrue(skill.speak_dialog.called)
        skill.speak_dialog.assert_called_with('tell me a color',
                                              {},
                                              expect_response=True,
                                              wait=True)

    def test_get_response_no_dialog(self):
        """Check that when no dialog/text is provided listening is triggered.
        """
        skill = create_skill()
        skill._wait_response = mock.Mock()
        skill.speak_dialog = mock.Mock()

        expected_response = 'ice creamr please'
        skill._wait_response.return_value = expected_response
        response = skill.get_response()
        self.assertEqual(response, expected_response)
        self.assertFalse(skill.speak_dialog.called)
        self.assertTrue(skill.bus.emit.called)
        sent_message = skill.bus.emit.call_args[0][0]
        self.assertEqual(sent_message.msg_type, 'mycroft.mic.listen')

    def test_get_response_validator(self):
        """Ensure validator is passed on."""
        skill = create_skill()
        skill._wait_response = mock.Mock()
        skill.speak_dialog = mock.Mock()

        def validator(*args, **kwargs):
            return True

        expected_response = 'ice creamr please'
        skill._wait_response.return_value = expected_response
        response = skill.get_response('what do you want',
                                      validator=validator)
        skill._wait_response.assert_called_with(AnyCallable(), validator,
                                                AnyCallable(), -1)

    def test_converse_detection(self):
        """Ensure validator is passed on."""
        skill = create_skill()
        skill._wait_response = mock.Mock()
        skill.speak_dialog = mock.Mock()

        def validator(*args, **kwargs):
            self.assertTrue(skill._converse_is_implemented)

        self.assertFalse(skill.converse_is_implemented)
        skill.get_response('what do you want', validator=validator)
        skill._wait_response.assert_called_with(AnyCallable(), validator,
                                                AnyCallable(), -1)
        self.assertFalse(skill.converse_is_implemented)


class TestMycroftSkillAskYesNo(TestCase):
    def test_ask_yesno_no(self):
        """Check that a negative response is interpreted as a no."""
        skill = create_skill()
        skill.get_response = mock.Mock()

        for ans in ['nope',
                    "i think not",
                    "don't think so",
                    "no",
                    "no, I obviously hate it",
                    "yes, but actually, no",
                    "wrong answer",
                    "yes, yes, yes, but actually, no",
                    "please don't",
                    "no! please! I beg you",
                    "yes, i don't want it for sure",
                    "it's a lie",
                    "that's certainly undesirable",
                    "he is lying",
                    "no, it's a lie",
                    "you are mistaken",
                    "that's a mistake"]:
            skill.get_response.return_value = ans
            response = skill.ask_yesno('Do you like breakfast')
            self.assertEqual(response, 'no')

    def test_ask_yesno_yes(self):
        """Check that an affirmative response is interpreted as a yes."""
        skill = create_skill()
        skill.get_response = mock.Mock()

        for ans in ['yes',
                    "that's affirmative",
                    "no, but actually, yes",
                    "i want it for sure", "obviously",
                    "please",
                    "yes, it's a lie",
                    "indeed",
                    "tou are not wrong"
                    "correct, he is lying",
                    "he is not lying",
                    "you are not mistaken"
                    "it's not a lie",
                    "do I hate it when companies sell my data? yes, that's certainly undesirable",
                    "please! I beg you"]:
            skill.get_response.return_value = ans
            response = skill.ask_yesno('Do you like breakfast')
            self.assertEqual(response, 'yes')

    def test_ask_yesno_other(self):
        """Check that non yes no response gets returned."""
        skill = create_skill()
        skill.get_response = mock.Mock()
        skill.get_response.return_value = 'I am a fish'

        response = skill.ask_yesno('Do you like breakfast')
        self.assertEqual(response, 'I am a fish')

    @mock.patch('ovos_workshop.skills.ovos.dig_for_message')
    def test_ask_yesno_german(self, dig_mock):
        """Check that when the skill is set to german it responds to "ja"."""
        # lang is session based, it comes from originating message in ovos-core
        dig_mock.return_value = Message("", {"lang": "de-de"})

        load_language("de-de")
        skill = create_skill(lang='de-de')
        skill.get_response = mock.Mock()
        skill.get_response.return_value = 'ja'

        response = skill.ask_yesno('Do you like breakfast')
        self.assertEqual(response, 'yes')


class TestMycroftAskSelection(TestCase):
    def test_selection_number(self):
        """Test selection by number."""
        skill = create_skill()
        skill.speak = mock.Mock()
        skill.get_response = mock.Mock()

        skill.get_response.return_value = 'the third'

        options = ['a balloon', 'an octopus', 'a piano']
        response = skill.ask_selection(options, 'which is better')
        self.assertEqual(options[2], response)

        # Assert that the spoken sentence contains all options.
        spoken_sentence = skill.speak.call_args[0][0]
        for opt in options:
            self.assertTrue(opt in spoken_sentence)

    def test_selection_last(self):
        """Test selection by "last"."""
        skill = create_skill()
        skill.speak = mock.Mock()
        skill.get_response = mock.Mock()

        skill.get_response.return_value = 'last one'

        options = ['a balloon', 'an octopus', 'a piano']
        response = skill.ask_selection(options, 'which is better')
        self.assertEqual(options[2], response)

        # Assert that the spoken sentence contains all options.
        spoken_sentence = skill.speak.call_args[0][0]
        for opt in options:
            self.assertTrue(opt in spoken_sentence)

    def test_selection_name(self):
        """Test selection by name."""
        skill = create_skill()
        skill.speak = mock.Mock()
        skill.get_response = mock.Mock()

        skill.get_response.return_value = 'octopus'

        options = ['a balloon', 'an octopus', 'a piano']
        response = skill.ask_selection(options, 'which is better')
        self.assertEqual(options[1], response)

        # Assert that the spoken sentence contains all options.
        spoken_sentence = skill.speak.call_args[0][0]
        for opt in options:
            self.assertTrue(opt in spoken_sentence)
