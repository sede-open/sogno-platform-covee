from io import StringIO
import random
import time
import unittest
from threading import Lock
from dmu.dmu import dmu

STANDARD_SUBSET_ELEMENTS = {
    "level1Dict": {"level1": "testval"},
    "level2Dict": {"level1": {"level2": "testval"}},
    "list": [1, 2, 3],
    "string": "teststring",
    "number": 42,
}


class EqualityStream:
    def __init__(self, init: str) -> None:
        self.stream = StringIO(init)

    def __eq__(self, other):
        if isinstance(other, EqualityStream):
            return self.stream.getvalue() == other.stream.getvalue()
        return False


SPECIAL_ELEMENTS = {
    "binary": b"binary data \x42",
    "stream": EqualityStream("teststring"),
}


ALL_TEST_ELEMENTS = dict(STANDARD_SUBSET_ELEMENTS, **SPECIAL_ELEMENTS)


class TestBasicDMU(unittest.TestCase):
    """Tests the basic functionality of the dmu class (no extreme specific cases & threading tests)"""

    dmuObj = None

    def setUp(self) -> None:
        self.dmuObj = dmu()

    def tearDown(self) -> None:
        self.dmuObj.cleanup()

    def test_dmu_addElement(self):
        """Tests the addElm function by adding and reading elements of different types."""

        for name, value in ALL_TEST_ELEMENTS.items():
            result = self.dmuObj.addElm(
                name, value
            )  # what if we change the data afterwards anyways?
            self.assertEqual(result, True, f"Element {name} could not be added")
            self.assertEqual(
                self.dmuObj.getDataSubset(name),
                value,
                f"Data {name} could not be retrieved",
            )

    def test_dmu_addElmEvent(self):
        """Tests the addElmEvent function of the dmu class by adding elements and changing their values or their subelements values"""

        OVERRIDE_ELEMENTS = {
            "level1Dict": {"level1": "newval"},
            "level2Dict": {"level1": {"level2": "newval"}},
            "list": [3, 2, 1],
        }

        # --- setup ---

        mutex = Lock()
        events_triggered = 0

        # prepare elements
        for name, value in STANDARD_SUBSET_ELEMENTS.items():
            self.assertTrue(
                self.dmuObj.addElm(name, value), f"Element {name} could not be added"
            )

        # prepare handlers
        def dict_handler(data, uuid, name, args, context):
            nonlocal events_triggered
            nonlocal mutex
            with mutex:
                events_triggered += 1

            handler_name = context["handler_name"]
            print(f"{handler_name}: {data}, {uuid}, {name}, {args}, {context}")

        def list_handler(data, uuid, name, args, context):
            nonlocal events_triggered
            nonlocal mutex
            with mutex:
                events_triggered += 1

            print(f"listHandler: {data}, {uuid}, {name}, {args}, {context}")

        uuids = [None] * 4

        # Add Event-Handlers
        uuids[0] = self.dmuObj.addElmEvent(
            dict_handler,
            "level2Dict",
            "level1",
            "level2",
            context={"handler_name": "level0Dict"},
        )
        uuids[1] = self.dmuObj.addElmEvent(
            dict_handler, "level1Dict", context={"handler_name": "level1Dict"}
        )
        uuids[2] = self.dmuObj.addElmEvent(
            dict_handler, "level2Dict", "level1", context={"handler_name": "level2Dict"}
        )
        uuids[3] = self.dmuObj.addElmEvent(
            list_handler, "list", context={"handler_name": "list"}
        )

        # test creation
        for res in uuids:
            self.assertTrue(res, "handler creation should succeed")

        # --- test update ---
        self.assertTrue(
            self.dmuObj.setDataSubset(OVERRIDE_ELEMENTS["level1Dict"], "level1Dict"),
            "Element level1Dict could not be changed",
        )
        self.assertTrue(
            self.dmuObj.setDataSubset(
                OVERRIDE_ELEMENTS["level2Dict"]["level1"], "level2Dict", "level1"
            ),
            "Element level2Dict/level1 could not be changed",
        )
        self.assertTrue(
            self.dmuObj.setDataSubset(OVERRIDE_ELEMENTS["list"], "list"),
            "Element list could not be changed",
        )
        self.assertTrue(
            self.dmuObj.setDataSubset("betterval", "level2Dict", "level1", "level2"),
            "Element level2Dict/level1/level2 could not be changed",
        )

        time.sleep(0.1)

        # --- cleanup ---
        self.dmuObj.cleanup()

        # --- assertions ---
        print(f"Events triggered: {events_triggered}")
        with mutex:
            if events_triggered != 4:
                print("Timeout reached")
                self.fail("Timeout reached and no event was triggered")

    def test_dmu_cleanup(self):
        """Test DMU Cleanup by adding elements and checking if they are removed afterwards"""
        # --- setup ---
        for name, value in STANDARD_SUBSET_ELEMENTS.items():
            self.assertTrue(
                self.dmuObj.addElm(name, value), f"Element {name} could not be added"
            )

        # --- test ---
        self.dmuObj.cleanup()

        # --- assertions ---
        for name in STANDARD_SUBSET_ELEMENTS.items():
            self.assertFalse(
                self.dmuObj.elmExists(name), f"Element {name} was not removed"
            )

    def test_dmu_cleanup_handlers(self):
        """Simple test to check if all handlers are removed after cleanup"""

        # --- setup ---
        for name, value in STANDARD_SUBSET_ELEMENTS.items():
            self.assertTrue(
                self.dmuObj.addElm(name, value), f"Element {name} could not be added"
            )

        def dict_handler(data, uuid, name, args, context):
            self.fail("Handler was triggered after cleanup")

        def list_handler(data, uuid, name, args, context):
            self.fail("Handler was triggered after cleanup")

        # add handlers
        self.dmuObj.addElmEvent(
            dict_handler, "level1Dict", context={"handler_name": "level1Dict"}
        )
        self.dmuObj.addElmEvent(
            dict_handler, "level2Dict", "level1", context={"handler_name": "level2Dict"}
        )
        self.dmuObj.addElmEvent(list_handler, "list")

        self.dmuObj.cleanup()

    def test_dmu_addSubElm(self):
        # test subset error on empty dmu
        test_dict = {"test": "value"}
        ret = self.dmuObj.addSubElm(test_dict, "nonexistant")
        self.assertEqual(ret, -2, "addSubElm should return -2 as error an indicator")

        # test successfull subset
        self.dmuObj.addElm("testElm", {})
        ret = self.dmuObj.addSubElm({"test": "value"}, "testElm")
        self.assertEqual(
            ret, -1, "addSubElm should return -1 as successful dict insert"
        )
        self.assertDictEqual(
            test_dict,
            self.dmuObj.getDataSubset("testElm"),
            "data should be as expected",
        )

        ret = self.dmuObj.addSubElm({"test": "value"}, "testElm", "test")
        self.assertEqual(
            ret, -1, "addSubElm should return -1 as successful dict insert"
        )
        self.assertDictEqual(
            test_dict,
            self.dmuObj.getDataSubset("testElm", "test"),
            "data should be as expected",
        )

        self.dmuObj.cleanup()

    def test_dmu_benchmark_basic_dict_element_ops(
        self, enabled=False, element_count=1000, iteration_count=5
    ):
        """Simple benchmark to check the performance of the dmu class by using many elements in one large 1-level dict

        This works in 4 stages all with 10000 elements:
        //TODO: Add elements
        //TODO: Read elements and check
        //TODO: Update elements and check
        //TODO: Remove elements and check
        """
        if not enabled:
            return

        def _generate_dict(size):
            if size == 1 or size == 0:
                # base case: create dictionary with random number of elements
                return {
                    random.randint(1, 10): random.randint(1, 10)
                    for i in range(random.randint(1, 5))
                }
            else:
                # recursive case: create dictionary with nested dictionary(s)
                r = random.randint(1, 10000)
                r1 = r % 10
                r2 = (r - 10) % 10
                r3 = (r - 1000) % 10
                return {r1: r2, r3: _generate_dict(size - 1)}

        def _change_dict(my_dict):
            for key, value in my_dict.items():
                if isinstance(value, dict):
                    # recursively change values of nested dictionaries
                    _change_dict(value)
                else:
                    # change value to random number between 1 and 100
                    my_dict[key] = random.randint(1, 100)

        # --- setup ---
        # generate random elements
        elements = []
        for i in range(element_count):
            if i < element_count - 1000:
                elements.append({i: random.randint(1, 10000)})
            else:
                elements.append(_generate_dict(i % 100))

        # --- setup updateElm ---
        changed_elements = [{}] * element_count
        for i, elm in enumerate(elements):
            changed_elements[i] = copy.deepcopy(elm)
            _change_dict(changed_elements[i])

        times = [[0 for _ in range(5)]] * iteration_count

        for iteration in range(iteration_count):
            # --- test add ---
            t1 = time.perf_counter()

            for i in range(element_count):
                self.dmuObj.addElm(str(i), elements[i])

            t2 = time.perf_counter()

            times[iteration][0] = t2 - t1

            # --- test elmExists ---
            t1 = time.perf_counter()
            for i in range(element_count):
                self.assertTrue(
                    self.dmuObj.elmExists(str(i)), f"Element {i} was not added"
                )

            t2 = time.perf_counter()
            times[iteration][1] = t2 - t1

            # --- test getElm ---
            read_elements = [{}] * element_count
            t1 = time.perf_counter()
            for i in range(element_count):
                read_elements[i] = self.dmuObj.getDataSubset(str(i))

            t2 = time.perf_counter()
            times[iteration][2] = t2 - t1

            # check
            for i, elm in enumerate(read_elements):
                self.assertEqual(
                    elm, elements[i], f"Element {i} was not read correctly"
                )

            # --- test updateElm ---
            t1 = time.perf_counter()
            for i in range(element_count):
                self.dmuObj.setDataSubset(changed_elements[i], str(i))
            t2 = time.perf_counter()
            times[iteration][3] = t2 - t1

            # --- test remove ---
            t1 = time.perf_counter()
            for i in range(element_count - 1, -1, -1):
                self.dmuObj.rmElm(str(i))
            t2 = time.perf_counter()
            times[iteration][4] = t2 - t1

        # calculate benchmark results = average of all iterations
        benchmark_results = [0 for _ in range(5)]
        for i in range(5):
            benchmark_results[i] = (
                sum([times[j][i] for j in range(iteration_count)]) / iteration_count
            )

        print(f"Benchmark results: {benchmark_results}")

    def test_dmu_benchmark_ps_element_ops(self, seconds=5):
        """Simple benchmark to check the performance of the dmu class by using many elements in one large 1-level dict

        This works in 4 stages all with 10000 elements:
        //TODO: Add elements
        //TODO: Read elements and check
        //TODO: Update elements and check
        //TODO: Remove elements and check
        """

        count = 0

        t1 = time.perf_counter()
        while time.perf_counter() - t1 < seconds:
            self.dmuObj.addElm("test", {"test1": "test2", "test4": {"level2": "wow"}})
            if self.dmuObj.elmExists("test"):
                self.dmuObj.setDataSubset("test3", "test", "test1")
            else:
                self.fail("Element was not added correctly")

            if self.dmuObj.getDataSubset("test")["test1"] == "test3":
                self.dmuObj.rmElm("test")
            else:
                self.fail("Element was not updated correctly")

            count += 1

        print("Basic CRUD Operations per second: " + str(count / seconds))
