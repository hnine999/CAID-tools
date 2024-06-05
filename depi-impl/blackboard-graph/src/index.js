import ReactDOM from 'react-dom/client';
//
import App from './App';
// ----------------------------------------------------------------------

const rootEl = document.getElementById('root');
const { startResource, userPreferences } = rootEl.dataset;
const branchName = rootEl.dataset.branchName || 'main';

ReactDOM.createRoot(rootEl).render(
    <App
        isReadOnly={branchName !== 'main'}
        startBranchName={branchName}
        startResource={startResource && JSON.parse(startResource)}
        userPreferences={userPreferences ? JSON.parse(userPreferences) : {}}
    />
);
