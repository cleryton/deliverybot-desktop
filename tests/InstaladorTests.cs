// Exercita somente os formulários em memória: não instala nem modifica a conta Windows.
using System;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using System.Drawing;

class InstaladorTests {
    static void Exigir(bool condicao, string motivo) { if(!condicao) throw new Exception(motivo); }
    [STAThread] static int Main(string[] args) {
        try {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using(var novo=new Instalador(true)) {
                var modelo=novo.Controls.OfType<ComboBox>().Single();
                var estoque=novo.Controls.OfType<CheckBox>().Single(c=>c.Text.StartsWith("Controlar"));
                Exigir(modelo.Items.Count==4,"Modelos de comércio ausentes.");
                foreach(int indice in new int[]{0,1,2,3}) {
                    modelo.SelectedIndex=indice;
                    Exigir(estoque.Checked==(indice==0 || indice==3),"Padrão de estoque incorreto.");
                }
                estoque.Checked=false;
                Exigir(!estoque.Checked,"Usuário não consegue personalizar o estoque.");
                Exigir(novo.Controls.OfType<TextBox>().Single(c=>c.Multiline).MaxLength==1200,"Descrição sem limite.");
                Exigir(novo.Controls.OfType<TextBox>().Count()==3,"Campos iniciais ausentes.");
                if(args.Length>0) {
                    Directory.CreateDirectory(args[0]);
                    modelo.SelectedIndex=1;
                    novo.ShowInTaskbar=false;
                    novo.StartPosition=FormStartPosition.Manual;
                    novo.Location=new Point(-20000,-20000);
                    novo.Show();
                    Application.DoEvents();
                    using(var bitmap=new Bitmap(novo.Width,novo.Height)) {
                        novo.DrawToBitmap(bitmap,new Rectangle(0,0,novo.Width,novo.Height));
                        bitmap.Save(Path.Combine(args[0],"instalacao-nova.png"));
                    }
                    novo.Hide();
                }
            }
            using(var atualizacao=new Instalador(false)) {
                Exigir(!atualizacao.Controls.OfType<TextBox>().Any(),"Atualização está pedindo um perfil novo.");
                Exigir(atualizacao.Controls.OfType<Label>().Any(l=>l.Text.Contains("mantendo os produtos")),"Aviso de preservação ausente.");
            }
            Console.WriteLine("Instalador: 4 perfis, configuração individual e atualização preservada aprovados.");
            return 0;
        } catch(Exception exc) { Console.Error.WriteLine(exc.Message);return 1; }
    }
}
