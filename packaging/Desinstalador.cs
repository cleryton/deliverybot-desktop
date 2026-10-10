using System;
using System.IO;
using System.Windows.Forms;
using System.Diagnostics;
using Microsoft.Win32;

class Desinstalador {
    static readonly string Destino = Path.GetFullPath(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","DeliveryBot"));
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        if(args.Length == 0) {
            if(MessageBox.Show("Desinstalar o DeliveryBot?\n\nSeu estoque, pedidos e backups serão preservados. Feche o aplicativo antes de continuar.","DeliveryBot",MessageBoxButtons.YesNo,MessageBoxIcon.Question) != DialogResult.Yes)return;
            string tmp = Path.Combine(Path.GetTempPath(),"DeliveryBot-Desinstalar-"+Guid.NewGuid().ToString("N")+".exe");
            File.Copy(Application.ExecutablePath,tmp);
            Process.Start(new ProcessStartInfo(tmp,"--remover") {UseShellExecute=true,WindowStyle=ProcessWindowStyle.Hidden});
            return;
        }
        if(args.Length != 1 || args[0] != "--remover") return;
        try {
            // Caminho fixo da instalação; remove somente arquivos conhecidos. Dados ficam em outra pasta.
            foreach(string nome in new[]{"DeliveryBot.exe","DeliveryBot.ico","Desinstalar.exe"}) {
                string arquivo=Path.GetFullPath(Path.Combine(Destino,nome));
                if(Path.GetDirectoryName(arquivo) != Destino)throw new InvalidOperationException("Destino inválido.");
                if(File.Exists(arquivo))File.Delete(arquivo);
            }
            foreach(Environment.SpecialFolder pasta in new[]{Environment.SpecialFolder.DesktopDirectory,Environment.SpecialFolder.Programs}) {
                string atalho=Path.Combine(Environment.GetFolderPath(pasta),"DeliveryBot.lnk");
                if(File.Exists(atalho))File.Delete(atalho);
            }
            Registry.CurrentUser.DeleteSubKeyTree(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\DeliveryBot",false);
            if(Directory.Exists(Destino)&&Directory.GetFileSystemEntries(Destino).Length==0)Directory.Delete(Destino);
            MessageBox.Show("DeliveryBot desinstalado. Seus dados foram preservados na pasta DeliveryBot do usuário.","DeliveryBot");
        }catch(Exception exc){MessageBox.Show("Feche o DeliveryBot e tente novamente.\n\n"+exc.Message,"DeliveryBot",MessageBoxButtons.OK,MessageBoxIcon.Error);}
    }
}
