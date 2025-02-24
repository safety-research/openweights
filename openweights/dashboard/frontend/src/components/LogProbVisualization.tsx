import React, { useState, useEffect, useMemo } from 'react';
import {
    Box,
    Typography,
    Slider,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Paper,
    Dialog,
    DialogTitle,
    DialogContent,
} from '@mui/material';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend
);

interface LogProbEvent {
    type: 'logprobs';
    loss: number;
    global_step: number;
    file: string;
}

interface Token {
    token: string;
    token_id: number;
    logp: number;
}

interface LogProbData {
    messages: any[];
    tokens: Token[];
}

interface TokenHistory {
    steps: number[];
    logprobs: number[];
}

interface Props {
    events: LogProbEvent[];
    orgId: string;
    getFileContent: (fileId: string) => Promise<string>;
}

export const LogProbVisualization: React.FC<Props> = ({ events, orgId, getFileContent }) => {
    const [selectedDataset, setSelectedDataset] = useState<string>('');
    const [sequenceIndex, setSequenceIndex] = useState<number>(0);
    const [step, setStep] = useState<number>(0);
    const [logProbData, setLogProbData] = useState<{ [key: string]: { [step: number]: LogProbData[] } }>({});
    const [selectedToken, setSelectedToken] = useState<{ token: string; tokenId: number } | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);

    console.log('LogProbVisualization props:', { events, orgId });

    // Extract unique datasets and steps from events
    const datasets = useMemo(() => {
        console.log('Computing datasets from events:', events);
        const datasetSet = new Set<string>();
        events.forEach(event => {
            // Extract dataset name from the event
            const datasetKey = Object.keys(event).find(key => 
                key !== 'type' && key !== 'loss' && key !== 'global_step' && key !== 'file'
            );
            if (datasetKey) {
                console.log('Found dataset key:', datasetKey);
                datasetSet.add(datasetKey);
            }
        });
        const datasetsArray = Array.from(datasetSet);
        console.log('Available datasets:', datasetsArray);
        return datasetsArray;
    }, [events]);

    const steps = useMemo(() => {
        const stepsArray = events
            .filter(e => e.type === 'logprobs')
            .map(e => e.global_step)
            .sort((a, b) => a - b);
        console.log('Available steps:', stepsArray);
        return stepsArray;
    }, [events]);

    // Load log prob data for a specific step
    const loadLogProbData = async (event: LogProbEvent) => {
        try {
            console.log('Loading data for event:', event);
            const content = await getFileContent(event.file);
            console.log('Loaded file content:', content.substring(0, 200) + '...');
            const data = JSON.parse(content) as LogProbData[];
            
            // Find the dataset key
            const datasetKey = Object.keys(event).find(key => 
                key !== 'type' && key !== 'loss' && key !== 'global_step' && key !== 'file'
            ) || '';

            console.log('Setting data for dataset:', datasetKey, 'step:', event.global_step);
            setLogProbData(prev => ({
                ...prev,
                [datasetKey]: {
                    ...(prev[datasetKey] || {}),
                    [event.global_step]: data
                }
            }));
        } catch (error) {
            console.error('Error loading log prob data:', error);
        }
    };

    // Load data when events change
    useEffect(() => {
        console.log('Events changed, loading data...');
        if (events.length > 0 && datasets.length > 0) {
            setSelectedDataset(datasets[0]);
            events.forEach(event => {
                loadLogProbData(event);
            });
        }
    }, [events, datasets]);

    // Get token history for visualization
    const getTokenHistory = (tokenId: number): TokenHistory => {
        const history: TokenHistory = { steps: [], logprobs: [] };
        
        if (!selectedDataset) return history;

        Object.entries(logProbData[selectedDataset] || {}).forEach(([step, sequences]) => {
            const sequence = sequences[sequenceIndex];
            if (!sequence) return;

            const token = sequence.tokens.find(t => t.token_id === tokenId);
            if (token) {
                history.steps.push(Number(step));
                history.logprobs.push(token.logp);
            }
        });

        // Sort by steps
        const sorted = history.steps.map((step, i) => ({ step, logp: history.logprobs[i] }))
            .sort((a, b) => a.step - b.step);
        
        return {
            steps: sorted.map(s => s.step),
            logprobs: sorted.map(s => s.logp)
        };
    };

    // Convert logp to color
    const getColorFromLogP = (logp: number): string => {
        // Convert logp to probability (0 to 1)
        const prob = Math.exp(logp);
        // Create a red background that gets lighter (whiter) with higher probability
        return `rgba(255, ${Math.floor(255 * prob)}, ${Math.floor(255 * prob)}, 0.3)`;
    };

    const currentData = selectedDataset && step && logProbData[selectedDataset]?.[step]?.[sequenceIndex];
    const maxSequences = selectedDataset && step && logProbData[selectedDataset]?.[step]?.length || 0;

    console.log('Render state:', {
        selectedDataset,
        step,
        currentData: currentData ? 'present' : 'absent',
        maxSequences,
        logProbData: Object.keys(logProbData)
    });

    return (
        <Box sx={{ mt: 2 }}>
            <Typography variant="h6">Log Probability Visualization</Typography>
            
            {/* Controls */}
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <FormControl sx={{ minWidth: 200 }}>
                    <InputLabel>Dataset</InputLabel>
                    <Select
                        value={selectedDataset}
                        onChange={(e) => setSelectedDataset(e.target.value)}
                        label="Dataset"
                    >
                        {datasets.map(dataset => (
                            <MenuItem key={dataset} value={dataset}>{dataset}</MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <FormControl sx={{ minWidth: 200 }}>
                    <InputLabel>Sequence Index</InputLabel>
                    <Select
                        value={sequenceIndex}
                        onChange={(e) => setSequenceIndex(Number(e.target.value))}
                        label="Sequence Index"
                    >
                        {[...Array(maxSequences)].map((_, i) => (
                            <MenuItem key={i} value={i}>{i}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>

            <Box sx={{ px: 2, mb: 2 }}>
                <Typography gutterBottom>Step: {step}</Typography>
                <Slider
                    value={step}
                    onChange={(_, value) => setStep(value as number)}
                    min={Math.min(...steps)}
                    max={Math.max(...steps)}
                    step={null}
                    marks={steps.map(s => ({ value: s, label: s.toString() }))}
                />
            </Box>

            {/* Token visualization */}
            {currentData ? (
                <Paper sx={{ p: 2, mt: 2 }}>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {currentData.tokens.map((token, i) => (
                            <Box
                                key={i}
                                onClick={() => {
                                    setSelectedToken({ token: token.token, tokenId: token.token_id });
                                    setDialogOpen(true);
                                }}
                                sx={{
                                    cursor: 'pointer',
                                    p: 0.5,
                                    borderRadius: 1,
                                    backgroundColor: getColorFromLogP(token.logp),
                                    '&:hover': {
                                        outline: '1px solid blue'
                                    }
                                }}
                            >
                                <Typography variant="body2">
                                    {token.token}
                                </Typography>
                            </Box>
                        ))}
                    </Box>
                </Paper>
            ) : (
                <Typography>No data available for the selected parameters</Typography>
            )}

            {/* Token history dialog */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
                <DialogTitle>
                    Token History: {selectedToken?.token}
                </DialogTitle>
                <DialogContent>
                    {selectedToken && (
                        <Box sx={{ height: 400 }}>
                            <Line
                                data={{
                                    labels: getTokenHistory(selectedToken.tokenId).steps,
                                    datasets: [{
                                        label: 'Log Probability',
                                        data: getTokenHistory(selectedToken.tokenId).logprobs,
                                        borderColor: 'rgb(75, 192, 192)',
                                        tension: 0.1
                                    }]
                                }}
                                options={{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {
                                        title: {
                                            display: true,
                                            text: `Log Probability Evolution for Token: ${selectedToken.token}`
                                        }
                                    },
                                    scales: {
                                        y: {
                                            title: {
                                                display: true,
                                                text: 'Log Probability'
                                            }
                                        },
                                        x: {
                                            title: {
                                                display: true,
                                                text: 'Training Step'
                                            }
                                        }
                                    }
                                }}
                            />
                        </Box>
                    )}
                </DialogContent>
            </Dialog>
        </Box>
    );
};