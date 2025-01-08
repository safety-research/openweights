import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import { Box, Typography, CircularProgress } from '@mui/material';
import { api } from '../../api';

interface Event {
    data: Record<string, any>;
}

interface MetricsPlotsProps {
    orgId: string;
    runId: string;
}

export const MetricsPlots: React.FC<MetricsPlotsProps> = ({ orgId, runId }) => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [plots, setPlots] = useState<Array<{
        title: string;
        x: number[];
        y: number[];
    }>>([]);

    useEffect(() => {
        const fetchAndProcessEvents = async () => {
            try {
                const events = await api.getRunEvents(orgId, runId);
                
                // Convert events to DataFrame-like structure
                const data: Record<string, any[]> = {};
                events.forEach((event: Event) => {
                    Object.entries(event.data).forEach(([key, value]) => {
                        if (!data[key]) {
                            data[key] = [];
                        }
                        data[key].push(value);
                    });
                });

                // Create plots for numerical metrics with steps
                const newPlots = [];
                if (data['step']) {
                    for (const [key, values] of Object.entries(data)) {
                        if (key === 'step') continue;
                        
                        // Check if all values are numbers
                        const isNumeric = values.every(v => 
                            typeof v === 'number' || 
                            (typeof v === 'string' && !isNaN(Number(v)))
                        );

                        if (isNumeric) {
                            // Filter out any null/undefined pairs
                            const validIndices = values.map((_, i) => i).filter(i => 
                                data.step[i] != null && values[i] != null
                            );
                            
                            if (validIndices.length > 1) {  // Need at least 2 points for a line
                                newPlots.push({
                                    title: key,
                                    x: validIndices.map(i => data.step[i]),
                                    y: validIndices.map(i => Number(values[i]))
                                });
                            }
                        }
                    }
                }

                setPlots(newPlots);
                setLoading(false);
            } catch (error) {
                console.error('Error fetching events:', error);
                setError(error instanceof Error ? error.message : 'Error fetching metrics');
                setLoading(false);
            }
        };

        fetchAndProcessEvents();
    }, [orgId, runId]);

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography color="error">Error loading metrics: {error}</Typography>
            </Box>
        );
    }

    if (plots.length === 0) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography>No metrics data available for plotting</Typography>
            </Box>
        );
    }

    return (
        <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>Metrics:</Typography>
            <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))',
                gap: 3
            }}>
                {plots.map((plot, index) => (
                    <Box key={index} sx={{ minHeight: 400 }}>
                        <Plot
                            data={[
                                {
                                    x: plot.x,
                                    y: plot.y,
                                    type: 'scatter',
                                    mode: 'lines+markers',
                                    name: plot.title,
                                }
                            ]}
                            layout={{
                                title: {
                                    text: plot.title,
                                    y: 0.95,  // Move title down slightly
                                    x: 0.05,  // Align title to the left
                                    xanchor: 'left',
                                    yanchor: 'top',
                                },
                                xaxis: { 
                                    title: 'Step',
                                    showgrid: true,
                                    gridcolor: '#E1E5EA',
                                },
                                yaxis: { 
                                    title: plot.title,
                                    showgrid: true,
                                    gridcolor: '#E1E5EA',
                                },
                                autosize: true,
                                margin: { 
                                    t: 60,  // Increased top margin
                                    r: 10,
                                    l: 60,
                                    b: 50
                                },
                                plot_bgcolor: 'white',
                                paper_bgcolor: 'white',
                                showlegend: false,  // Hide legend since we only have one trace
                                modebar: {
                                    orientation: 'v',  // Place modebar vertically
                                    bgcolor: 'transparent'
                                }
                            }}
                            style={{ width: '100%', height: '100%' }}
                            config={{
                                responsive: true,
                                displayModeBar: true,
                                displaylogo: false,  // Hide plotly logo
                                modeBarButtonsToAdd: ['toImage'],
                                modeBarButtonsToRemove: ['select2d', 'lasso2d'],
                                toImageButtonOptions: {
                                    format: 'png',
                                    filename: `${plot.title}_${runId}`,
                                    height: 800,
                                    width: 1200,
                                    scale: 2
                                }
                            }}
                        />
                    </Box>
                ))}
            </Box>
        </Box>
    );
};