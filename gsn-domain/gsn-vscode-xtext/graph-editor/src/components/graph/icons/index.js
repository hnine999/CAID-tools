import Assumption from './Assumption';
import Context from './Context';
import Goal from './Goal';
import Justification from './Justification';
import Solution from './Solution';
import Strategy from './Strategy';
import InContextOf from './InContextOf';
import SolvedBy from './SolvedBy';

export { Assumption };
export { Justification };
export { Context };
export { Goal };
export { Solution };
export { Strategy };
export { InContextOf };
export { SolvedBy };

export default {
    Assumption,
    Justification,
    Goal,
    Solution,
    Strategy,
    Context,
    inContextOf: InContextOf,
    solvedBy: SolvedBy,
};
