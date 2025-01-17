from types import GeneratorType
import typing as t
from .runner import Runner
from .runner import RunnerImpl
from .runner import RunnerState
from .runner import SimpleRunner
from ..runner.utils import Params
from ..runner.container import AutoContainer


class LocalRunner(RunnerImpl):
    def setup(self) -> None:
        if self._state != RunnerState.INIT:
            return
        self._state = RunnerState.SETTING
        self._runner._setup()  # type: ignore[reportPrivateUsage]
        self._state = RunnerState.SET

    async def async_run(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return self.run(*args, **kwargs)

    async def async_run_batch(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return self.run_batch(*args, **kwargs)

    def run(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if self._state is RunnerState.INIT:
            self.setup()
        if isinstance(self._runner, Runner):
            params = Params(*args, **kwargs)
            params = params.map(
                lambda i: AutoContainer.singles_to_batch(
                    [i],
                    batch_axis=self._runner.batch_options.input_batch_axis,
                )
            )
            batch_result = self._runner._run_batch(  # type: ignore[reportPrivateUsage]
                *params.args, **params.kwargs
            )
            single_results = AutoContainer.batch_to_singles(
                batch_result,
                batch_axis=self._runner.batch_options.output_batch_axis,
            )
            if isinstance(single_results, GeneratorType):
                # A runner may mistakenly return a generator, causing 
                # indexing & pickling errors downstream.
                single_results = list(single_results)

            return single_results[0]

        if isinstance(self._runner, SimpleRunner):
            return self._runner._run(*args, **kwargs)  # type: ignore[reportPrivateUsage]

    def run_batch(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if self._state is RunnerState.INIT:
            self.setup()
        if isinstance(self._runner, Runner):
            return self._runner._run_batch(*args, **kwargs)  # type: ignore[reportPrivateUsage]
        if isinstance(self._runner, SimpleRunner):
            raise RuntimeError("shall not call run_batch on a" " simple runner")
