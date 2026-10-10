param([Parameter(Mandatory=$true)][string]$BankHost)
# Capture certificates presented during validation; reject every validation error.
# Does not add a trusted CA, disable TLS validation, or send HTTP requests.
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography.X509Certificates;
public class BankChainInspector {
    public static List<string> Inspect(string host) {
        var output = new List<string>();
        using (var tcp = new TcpClient()) {
            var task = tcp.ConnectAsync(host, 443);
            if (!task.Wait(8000)) { output.Add("TCP timeout"); return output; }
            tcp.ReceiveTimeout = 8000; tcp.SendTimeout = 8000;
            using (var tls = new SslStream(tcp.GetStream(), false,
                (sender, cert, chain, errors) => {
                    output.Add("PolicyErrors=" + errors);
                    if (chain != null) {
                        foreach (var status in chain.ChainStatus)
                            output.Add("ChainStatus=" + status.Status);
                        foreach (var element in chain.ChainElements) {
                            var c = element.Certificate;
                            output.Add("Subject=" + c.Subject + "; Issuer=" + c.Issuer
                                + "; SHA1=" + c.Thumbprint + "; NotAfter="
                                + c.NotAfter.ToUniversalTime().ToString("o"));
                        }
                    }
                    return errors == SslPolicyErrors.None;
                })) {
                try { tls.AuthenticateAsClient(host, null, SslProtocols.Tls12, true);
                      output.Add("Verified=true"); }
                catch (Exception ex) { output.Add("Rejected=" + ex.GetType().Name); }
            }
        }
        return output;
    }
}
'@
[BankChainInspector]::Inspect($BankHost)
