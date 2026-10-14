function Enable-GitHubSystemProxy {
    # Go-based gh does not automatically use Windows Internet Settings proxies.
    # Reuse the user's configured route; never disable TLS or alter system settings.
    if (!$env:HTTPS_PROXY) {
        $configuredProxy=[System.Net.WebRequest]::DefaultWebProxy.GetProxy([Uri]'https://github.com')
        if ($configuredProxy.Host -ne 'github.com' -and $configuredProxy.Scheme -in @('http','https')) {
            $env:HTTPS_PROXY=$configuredProxy.AbsoluteUri
        }
    }
}
