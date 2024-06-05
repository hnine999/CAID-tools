import { useMemo } from 'react';
import { Handle, Position } from 'reactflow';

export default function useAggregateHandles(isExpanded, orientation) {
    const handles = useMemo(() => {
        if (isExpanded) {
            return null;
        }

        const leftOrRight = orientation === 'left' ? Position.Right : Position.Left;

        return (
            <>
                <Handle
                    style={{ marginTop: 5, backgroundColor: '#fff', border: '1px solid #4e4e4e' }}
                    type="source"
                    position={leftOrRight}
                    isConnectable={false}
                />
                <Handle
                    style={{ marginTop: -5, backgroundColor: '#4e4e4e', border: '1px solid #4e4e4e' }}
                    type="target"
                    position={leftOrRight}
                    isConnectable={false}
                />
            </>
        );
    }, [isExpanded, orientation]);

    return handles;
}
