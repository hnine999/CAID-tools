// https://github.com/irvanherz/use-awaitable-component
import { useState } from 'react';

export default function useAwaitableComponent() {
    const [data, setData] = useState({ status: 'idle', resolve: null });

    const handleResolve = (val) => {
        if (data.status !== 'awaiting') {
            throw new Error('Awaitable component is not awaiting.');
        }
        data.resolve?.(val);
        setData({ status: 'resolved', resolve: null });
    };

    const handleReset = () => {
        setData({ status: 'idle', resolve: null });
    };

    const handleExecute = async () =>
        new Promise((resolve) => {
            setData({ status: 'awaiting', resolve });
        });

    return [data.status, handleExecute, handleResolve, handleReset];
}
