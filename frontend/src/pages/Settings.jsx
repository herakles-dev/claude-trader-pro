import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { systemAPI, aiProviderAPI } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import toast from 'react-hot-toast'

function Settings() {
  const queryClient = useQueryClient()
  const { connected, disconnect, connect } = useWebSocket({ autoConnect: false })

  const [settings, setSettings] = useState({
    default_symbol: 'BTC',
    trading_strategy: 'conservative',
    auto_refresh_interval: 30,
    notifications_enabled: true,
    dark_mode: true,
  })

  // Load settings from localStorage on mount
  useEffect(() => {
    const saved = {
      default_symbol: localStorage.getItem('default_symbol') || 'BTC',
      trading_strategy: localStorage.getItem('trading_strategy') || 'conservative',
      auto_refresh_interval: parseInt(localStorage.getItem('auto_refresh_interval') || '30'),
      notifications_enabled: localStorage.getItem('notifications_enabled') !== 'false',
      dark_mode: localStorage.getItem('dark_mode') !== 'false',
    }
    setSettings(saved)
  }, [])

  const { data: config } = useQuery(
    'system-config',
    () => systemAPI.getConfig(),
    {
      select: (res) => res.data,
      onError: () => {
        // Config endpoint might not exist, that's okay
      },
    }
  )

  // AI Provider query
  const { data: aiProviders, isLoading: aiProvidersLoading } = useQuery(
    'ai-providers',
    () => aiProviderAPI.getProviders(),
    {
      select: (res) => res.data,
      refetchInterval: 30000, // Refresh every 30 seconds
    }
  )

  // Set AI provider mutation
  const setAiProviderMutation = useMutation(
    (provider) => aiProviderAPI.setProvider(provider),
    {
      onSuccess: (_, provider) => {
        toast.success(`AI provider switched to ${provider}`)
        queryClient.invalidateQueries('ai-providers')
      },
      onError: (error) => {
        toast.error(`Failed to switch AI provider: ${error.message}`)
      },
    }
  )

  const updateConfigMutation = useMutation(
    (newConfig) => systemAPI.updateConfig(newConfig),
    {
      onSuccess: () => {
        toast.success('Settings saved successfully')
        queryClient.invalidateQueries('system-config')
      },
      onError: () => {
        toast.error('Failed to save settings')
      },
    }
  )

  const handleChange = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = () => {
    // Save to localStorage
    Object.entries(settings).forEach(([key, value]) => {
      localStorage.setItem(key, value.toString())
    })

    // Try to save to backend
    updateConfigMutation.mutate(settings)
  }

  const handleReset = () => {
    const defaults = {
      default_symbol: 'BTC',
      trading_strategy: 'conservative',
      auto_refresh_interval: 30,
      notifications_enabled: true,
      dark_mode: true,
    }
    setSettings(defaults)
    localStorage.clear()
    toast.success('Settings reset to defaults')
  }

  const toggleWebSocket = () => {
    if (connected) {
      disconnect()
      toast.success('WebSocket disconnected')
    } else {
      connect()
      toast.success('WebSocket connecting...')
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 mt-1">
          Configure your trading preferences and system options
        </p>
      </div>

      {/* Trading Preferences */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-bold text-white border-b border-gray-700 pb-3">
          Trading Preferences
        </h2>

        <div className="space-y-4">
          {/* Default Symbol */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Default Symbol
            </label>
            <select
              value={settings.default_symbol}
              onChange={(e) => handleChange('default_symbol', e.target.value)}
              className="select-field"
            >
              <option value="BTC">Bitcoin (BTC)</option>
              <option value="ETH">Ethereum (ETH)</option>
              <option value="SOL">Solana (SOL)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              The cryptocurrency to display by default
            </p>
          </div>

          {/* Trading Strategy */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Trading Strategy
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => handleChange('trading_strategy', 'conservative')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  settings.trading_strategy === 'conservative'
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                }`}
              >
                <div className="font-semibold text-white mb-1">
                  Conservative
                </div>
                <div className="text-xs text-gray-400">
                  Lower risk, higher confidence threshold
                </div>
              </button>

              <button
                onClick={() => handleChange('trading_strategy', 'aggressive')}
                className={`p-4 rounded-lg border-2 transition-all ${
                  settings.trading_strategy === 'aggressive'
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                }`}
              >
                <div className="font-semibold text-white mb-1">Aggressive</div>
                <div className="text-xs text-gray-400">
                  Higher risk, more frequent predictions
                </div>
              </button>
            </div>
          </div>

          {/* Auto Refresh Interval */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Auto Refresh Interval (seconds)
            </label>
            <input
              type="number"
              min="10"
              max="300"
              step="10"
              value={settings.auto_refresh_interval}
              onChange={(e) =>
                handleChange('auto_refresh_interval', parseInt(e.target.value))
              }
              className="input-field"
            />
            <p className="text-xs text-gray-500 mt-1">
              How often to refresh market data (10-300 seconds)
            </p>
          </div>
        </div>
      </div>

      {/* AI Provider Selection */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-bold text-white border-b border-gray-700 pb-3">
          AI Provider
        </h2>

        <div className="space-y-4">
          <p className="text-sm text-gray-400">
            Select the AI model for generating trading predictions. Claude offers
            deeper analysis while Gemini is faster and more cost-effective.
          </p>

          {aiProvidersLoading ? (
            <div className="flex items-center space-x-2 text-gray-400">
              <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
              <span>Loading providers...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {aiProviders?.providers?.map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => setAiProviderMutation.mutate(provider.id)}
                  disabled={!provider.available || setAiProviderMutation.isLoading}
                  className={`p-4 rounded-lg border-2 transition-all text-left ${
                    provider.is_default
                      ? 'border-blue-500 bg-blue-900/20'
                      : provider.available
                      ? 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                      : 'border-gray-800 bg-gray-900/50 opacity-50 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="font-semibold text-white">{provider.name}</div>
                    <div className="flex items-center space-x-2">
                      {provider.is_default && (
                        <span className="text-xs bg-blue-600 px-2 py-0.5 rounded text-white">
                          Active
                        </span>
                      )}
                      <div
                        className={`w-2 h-2 rounded-full ${
                          provider.available ? 'bg-green-400' : 'bg-red-400'
                        }`}
                      />
                    </div>
                  </div>
                  <div className="text-xs text-gray-400">{provider.model}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {provider.id === 'claude'
                      ? '~$0.01/prediction - Detailed analysis'
                      : '~$0.0003/prediction - Fast & efficient'}
                  </div>
                </button>
              ))}
            </div>
          )}

          {aiProviders?.current_provider && (
            <div className="text-sm text-gray-500">
              Current provider:{' '}
              <span className="text-blue-400 font-medium">
                {aiProviders.current_provider}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* System Options */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-bold text-white border-b border-gray-700 pb-3">
          System Options
        </h2>

        <div className="space-y-4">
          {/* Notifications */}
          <div className="flex items-center justify-between p-4 bg-gray-900/50 rounded-lg">
            <div>
              <div className="font-medium text-white">Enable Notifications</div>
              <div className="text-sm text-gray-400">
                Show toast notifications for predictions and alerts
              </div>
            </div>
            <button
              onClick={() =>
                handleChange('notifications_enabled', !settings.notifications_enabled)
              }
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                settings.notifications_enabled ? 'bg-blue-600' : 'bg-gray-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  settings.notifications_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Dark Mode */}
          <div className="flex items-center justify-between p-4 bg-gray-900/50 rounded-lg">
            <div>
              <div className="font-medium text-white">Dark Mode</div>
              <div className="text-sm text-gray-400">
                Use dark theme (light mode coming soon)
              </div>
            </div>
            <button
              onClick={() => handleChange('dark_mode', !settings.dark_mode)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                settings.dark_mode ? 'bg-blue-600' : 'bg-gray-600'
              }`}
              disabled
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  settings.dark_mode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* WebSocket Connection */}
          <div className="flex items-center justify-between p-4 bg-gray-900/50 rounded-lg">
            <div>
              <div className="font-medium text-white">WebSocket Connection</div>
              <div className="text-sm text-gray-400 flex items-center space-x-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    connected ? 'bg-green-400' : 'bg-red-400'
                  }`}
                />
                <span>{connected ? 'Connected' : 'Disconnected'}</span>
              </div>
            </div>
            <button onClick={toggleWebSocket} className="btn-secondary">
              {connected ? 'Disconnect' : 'Connect'}
            </button>
          </div>
        </div>
      </div>

      {/* API Configuration */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xl font-bold text-white border-b border-gray-700 pb-3">
          API Configuration
        </h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              API Base URL
            </label>
            <div className="input-field bg-gray-900 cursor-not-allowed">
              {config?.api_url || 'http://localhost:8100/api'}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              WebSocket URL
            </label>
            <div className="input-field bg-gray-900 cursor-not-allowed">
              {config?.ws_url || 'http://localhost:8100'}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">
              API Version
            </label>
            <div className="input-field bg-gray-900 cursor-not-allowed">
              {config?.version || 'v1.0.0'}
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <button onClick={handleReset} className="btn-secondary">
          Reset to Defaults
        </button>

        <div className="flex space-x-3">
          <button
            onClick={() => window.location.reload()}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={updateConfigMutation.isLoading}
            className="btn-primary"
          >
            {updateConfigMutation.isLoading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Settings
