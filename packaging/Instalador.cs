using System;
using System.IO;
using System.Drawing;
using System.Reflection;
using System.Windows.Forms;
using System.Diagnostics;
using Microsoft.Win32;
using System.Text;
using System.Collections.Generic;
using System.Web.Script.Serialization;

class Instalador : Form {
    static readonly string Destino = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "DeliveryBot");
    const string Registro = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\DeliveryBot";
    Label info;
    Button instalar;
    CheckBox abrir;
    bool novaLoja;
    TextBox nome, segmento, descricao;
    ComboBox modelo;
    CheckBox estoque;
    static readonly string Dados = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DeliveryBot");
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Instalador());
    }
    public Instalador(bool? comercioNovo = null) {
        Text = "Instalar DeliveryBot";
        novaLoja = comercioNovo ?? !File.Exists(Path.Combine(Dados, "deliverybot.db"));
        ClientSize = new Size(590, novaLoja ? 650 : 350);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(246,248,247);
        Font = new Font("Segoe UI", 10);
        Label titulo = new Label { Text = "DeliveryBot", Font = new Font("Segoe UI", 27, FontStyle.Bold), ForeColor = Color.FromArgb(24,125,100), Location = new Point(28,25), AutoSize = true };
        info = new Label { Text = novaLoja ? "Conte como seu comércio funciona. Você poderá mudar esse perfil\nno aplicativo. Não é necessário instalar Python, Node.js ou Docker." : "Atualize seu aplicativo mantendo os produtos, pedidos e configurações.\n\nA instalação cria atalhos na área de trabalho e no menu Iniciar.\n\nInstalação para este usuário:\n" + Destino, Location = new Point(32,92), Size = new Size(525,novaLoja ? 52 : 170) };
        if (novaLoja) {
            Controls.Add(new Label {Text="Nome do comércio",Location=new Point(32,155),AutoSize=true});
            nome=new TextBox {Location=new Point(32,179),Size=new Size(525,30),MaxLength=160};
            Controls.Add(new Label {Text="Segmento (restaurante, oficina, loja de roupas…)",Location=new Point(32,220),AutoSize=true});
            segmento=new TextBox {Location=new Point(32,244),Size=new Size(525,30),MaxLength=120};
            Controls.Add(new Label {Text="O que você oferece e como atende?",Location=new Point(32,285),AutoSize=true});
            descricao=new TextBox {Location=new Point(32,309),Size=new Size(525,88),MaxLength=1200,Multiline=true,ScrollBars=ScrollBars.Vertical,AcceptsReturn=true};
            Controls.Add(new Label {Text="Como seu comércio funciona?",Location=new Point(32,410),AutoSize=true});
            modelo=new ComboBox {Location=new Point(32,435),Size=new Size(525,30),DropDownStyle=ComboBoxStyle.DropDownList};
            modelo.Items.AddRange(new object[]{"Revenda de produtos", "Produção sob pedido", "Prestação de serviços", "Produtos e serviços (misto)"});
            estoque=new CheckBox {Text="Controlar quantidade nos novos itens do catálogo",Checked=true,Location=new Point(32,477),AutoSize=true};
            modelo.SelectedIndexChanged += delegate {estoque.Checked=modelo.SelectedIndex==0 || modelo.SelectedIndex==3;};
            modelo.SelectedIndex=0;
            Controls.AddRange(new Control[]{nome,segmento,descricao,modelo,estoque});
            Controls.Add(new Label {Text="Produção e serviços começam sem contagem. Você pode controlar\nquantidades por item, como bebidas de um restaurante ou peças de oficina.\nEsses dados ficam neste computador.",Location=new Point(32,510),Size=new Size(525,65)});
        }
        abrir = new CheckBox { Text = "Abrir o aplicativo ao terminar", Checked = true, Location = new Point(32,novaLoja ? 600 : 284), AutoSize = true };
        instalar = new Button { Text = "Instalar", Location = new Point(430,novaLoja ? 594 : 278), Size = new Size(120,40), BackColor = Color.FromArgb(24,125,100), ForeColor = Color.White, FlatStyle = FlatStyle.Flat };
        instalar.Click += Instalar;
        Controls.AddRange(new Control[] {titulo,info,abrir,instalar});
    }
    static void Extrair(string recurso, string arquivo) {
        string tmp = arquivo + ".novo";
        using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream(recurso))
        using (FileStream output = File.Create(tmp)) { input.CopyTo(output); }
        try {
            if(File.Exists(arquivo)) File.Replace(tmp,arquivo,arquivo+".anterior",true);
            else File.Move(tmp,arquivo);
        }
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
        if(novaLoja && (String.IsNullOrWhiteSpace(nome.Text) || String.IsNullOrWhiteSpace(segmento.Text) || String.IsNullOrWhiteSpace(descricao.Text))) {
            MessageBox.Show("Preencha o nome, o segmento e uma descrição do comércio para começar.","Seu comércio",MessageBoxButtons.OK,MessageBoxIcon.Information);
            return;
        }
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
                key.SetValue("DisplayName","DeliveryBot"); key.SetValue("DisplayVersion","2.44.0");
                key.SetValue("Publisher","DeliveryBot"); key.SetValue("InstallLocation",Destino);
                key.SetValue("DisplayIcon",Path.Combine(Destino,"DeliveryBot.ico"));
                key.SetValue("UninstallString","\"" + Path.Combine(Destino,"Desinstalar.exe") + "\"");
                key.SetValue("NoModify",1,RegistryValueKind.DWord); key.SetValue("NoRepair",1,RegistryValueKind.DWord);
            }
            // Atualizações preservam o perfil e o banco existente.
            if(novaLoja && !File.Exists(Path.Combine(Dados,"deliverybot.db"))) {
                Directory.CreateDirectory(Dados);
                var perfil=new Dictionary<string,object> {{"nome",nome.Text.Trim()},{"segmento",segmento.Text.Trim()},{"descricao",descricao.Text.Trim()},{"modelo",new string[]{"REVENDA","PRODUCAO","SERVICOS","MISTO"}[modelo.SelectedIndex]},{"controlar_estoque",estoque.Checked}};
                string arquivo=Path.Combine(Dados,"perfil-instalacao.json");
                string temporario=arquivo+".novo";
                File.WriteAllText(temporario,new JavaScriptSerializer().Serialize(perfil),new UTF8Encoding(false));
                if(File.Exists(arquivo)) File.Replace(temporario,arquivo,null); else File.Move(temporario,arquivo);
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
