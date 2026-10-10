using System;
using System.IO;
using System.Drawing;
using System.Reflection;
using System.Windows.Forms;
using System.Diagnostics;
using Microsoft.Win32;

class Instalador : Form {
    static readonly string Destino = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "DeliveryBot");
    const string Registro = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\DeliveryBot";
    Label info;
    Button instalar;
    CheckBox abrir;
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Instalador());
    }
    public Instalador() {
        Text = "Instalar DeliveryBot";
        ClientSize = new Size(590, 350);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(246,248,247);
        Font = new Font("Segoe UI", 10);
        Label titulo = new Label { Text = "DeliveryBot", Font = new Font("Segoe UI", 27, FontStyle.Bold), ForeColor = Color.FromArgb(24,125,100), Location = new Point(28,25), AutoSize = true };
        info = new Label { Text = "Produtos, estoque e atendimento em um só aplicativo.\n\nA instalação cria um atalho na área de trabalho e no menu Iniciar.\nNão é necessário instalar Python ou executar comandos.\n\nInstalação para este usuário:\n" + Destino, Location = new Point(32,92), Size = new Size(525,170) };
        abrir = new CheckBox { Text = "Abrir o aplicativo ao terminar", Checked = true, Location = new Point(32,284), AutoSize = true };
        instalar = new Button { Text = "Instalar", Location = new Point(430,278), Size = new Size(120,40), BackColor = Color.FromArgb(24,125,100), ForeColor = Color.White, FlatStyle = FlatStyle.Flat };
        instalar.Click += Instalar;
        Controls.AddRange(new Control[] {titulo,info,abrir,instalar});
    }
    static void Extrair(string recurso, string arquivo) {
        string tmp = arquivo + ".novo";
        using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream(recurso))
        using (FileStream output = File.Create(tmp)) { input.CopyTo(output); }
        try { if(File.Exists(arquivo)) File.Delete(arquivo); File.Move(tmp,arquivo); }
        catch { if(File.Exists(tmp))File.Delete(tmp); throw; }
    }
    static void Atalho(string caminho, string executavel) {
        Type type = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(type);
        object shortcut = type.InvokeMember("CreateShortcut",BindingFlags.InvokeMethod,null,shell,new object[]{caminho});
        Type st = shortcut.GetType();
        st.InvokeMember("TargetPath",BindingFlags.SetProperty,null,shortcut,new object[]{executavel});
        st.InvokeMember("WorkingDirectory",BindingFlags.SetProperty,null,shortcut,new object[]{Destino});
        st.InvokeMember("Description",BindingFlags.SetProperty,null,shortcut,new object[]{"DeliveryBot — Gestão da loja"});
        st.InvokeMember("Save",BindingFlags.InvokeMethod,null,shortcut,null);
    }
    void Instalar(object sender, EventArgs ev) {
        instalar.Enabled = false;
        Cursor = Cursors.WaitCursor;
        try {
            Directory.CreateDirectory(Destino);
            string exe = Path.Combine(Destino,"DeliveryBot.exe");
            Extrair("aplicativo",exe);
            Extrair("desinstalador",Path.Combine(Destino,"Desinstalar.exe"));
            Extrair("icone",Path.Combine(Destino,"DeliveryBot.ico"));
            Atalho(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"DeliveryBot.lnk"),exe);
            Atalho(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs),"DeliveryBot.lnk"),exe);
            using(RegistryKey key = Registry.CurrentUser.CreateSubKey(Registro)) {
                key.SetValue("DisplayName","DeliveryBot"); key.SetValue("DisplayVersion","2.7.0");
                key.SetValue("Publisher","DeliveryBot"); key.SetValue("InstallLocation",Destino);
                key.SetValue("DisplayIcon",Path.Combine(Destino,"DeliveryBot.ico"));
                key.SetValue("UninstallString","\"" + Path.Combine(Destino,"Desinstalar.exe") + "\"");
                key.SetValue("NoModify",1,RegistryValueKind.DWord); key.SetValue("NoRepair",1,RegistryValueKind.DWord);
            }
            if(abrir.Checked) Process.Start(new ProcessStartInfo(exe) {UseShellExecute=true});
            MessageBox.Show("Instalação concluída. Use o atalho DeliveryBot para abrir sua loja.","DeliveryBot",MessageBoxButtons.OK,MessageBoxIcon.Information);
            Close();
        } catch(Exception exc) {
            MessageBox.Show("Não foi possível concluir a instalação. Feche o DeliveryBot se ele estiver aberto e tente novamente.\n\n"+exc.Message,"DeliveryBot",MessageBoxButtons.OK,MessageBoxIcon.Error);
            instalar.Enabled = true;
        } finally { Cursor=Cursors.Default; }
    }
}
