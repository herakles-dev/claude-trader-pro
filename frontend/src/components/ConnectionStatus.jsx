/**
 * Connection Status Component
 * Visual indicator of WebSocket connection status
 * Shows: Connected (green), Disconnected (red), Reconnecting (yellow)
 */

import React from 'react';
import { Box, Chip, Tooltip } from '@mui/material';
import { 
  FiberManualRecord as ConnectedIcon,
  Warning as WarningIcon,
  Error as ErrorIcon 
} from '@mui/icons-material';
import { useWebSocket } from '../context/WebSocketContext';

export default function ConnectionStatus() {
  const { connected, connecting } = useWebSocket();

  const getStatus = () => {
    if (connected) {
      return {
        label: 'Live',
        color: 'success',
        icon: <ConnectedIcon sx={{ fontSize: 12 }} />,
        tooltip: 'Connected to real-time updates'
      };
    } else if (connecting) {
      return {
        label: 'Connecting',
        color: 'warning',
        icon: <WarningIcon sx={{ fontSize: 12 }} />,
        tooltip: 'Attempting to connect...'
      };
    } else {
      return {
        label: 'Offline',
        color: 'error',
        icon: <ErrorIcon sx={{ fontSize: 12 }} />,
        tooltip: 'Disconnected from server'
      };
    }
  };

  const status = getStatus();

  return (
    <Tooltip title={status.tooltip} arrow>
      <Chip
        icon={status.icon}
        label={status.label}
        color={status.color}
        size="small"
        variant="outlined"
        sx={{
          height: 24,
          fontWeight: 'bold',
          fontSize: '0.75rem',
          '& .MuiChip-icon': {
            marginLeft: '8px'
          }
        }}
      />
    </Tooltip>
  );
}
