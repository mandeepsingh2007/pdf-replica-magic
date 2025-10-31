import { Navigation } from "@/components/Navigation";
import { SectionHeader } from "@/components/SectionHeader";
import { CTAButton } from "@/components/CTAButton";
import coverBooks from "@/assets/cover-books.png";
import layoutBooks from "@/assets/layout-books.png";
import illustrations from "@/assets/illustrations.png";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <main className="pt-32">
        {/* Meet Us Section */}
        <section id="meet-us" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <SectionHeader title="Meet Us" />
            <div className="p-8 bg-white flex gap-8">
              <div className="flex-1 space-y-4 text-foreground">
                <p>
                  We are a team of creative thinkers, passionate designers, and enthusiastic illustrators.
                </p>
                <p className="font-bold">
                  We are high skilled creative minds that are habitually involved in avant-garde 
                  design and illustration for children's literature. We are specialist in children's 
                  book design, illustration and layout.
                </p>
                <p>
                  Apart from school textbooks, storybooks, and activity books, we also make educational 
                  and interactive posters, and puzzles for children.
                </p>
                <p>
                  We are effortless graphic design studio that could innovate splendid quality of visuals 
                  in market competitive prices.
                </p>
                <p>
                  Our dedication for design also divergence into other forms of graphic design. We offer 
                  graphic design services for corporate identity communication including logo, stationery, 
                  brochure, poster, catalogue, flyer, standee, and the like.
                </p>
                <p>
                  So, whether you are starting up a new company, or eagerly want to establish your brand 
                  identity, NE Graphics is here to make all your dreams come true.
                </p>
              </div>
              <div className="flex flex-col justify-center items-center text-4xl font-bold text-foreground leading-tight">
                <div>Random</div>
                <div>Slide</div>
                <div>Show</div>
                <div>Our</div>
                <div>Work</div>
              </div>
            </div>
          </div>
        </section>

        {/* Cover Design Section */}
        <section id="cover-design" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <div className="bg-primary text-primary-foreground py-8 px-8 flex items-center justify-between">
              <div className="flex-1">
                <h2 className="text-4xl font-bold mb-4">ATTENTION-GRABBING</h2>
                <h2 className="text-4xl font-bold mb-6">COVERS DESIGNS</h2>
                <p className="mb-4 max-w-2xl">
                  It's our passion for creating beautifully finished illustrations that enables us to 
                  create books that are head and shoulders above the rest. We'll ensure that your book 
                  is the one that stands out on bookshelves, enticing readers to pick up and purchase a copy.
                </p>
                <p className="mb-8 max-w-2xl">
                  For an extra special touch, we work with incredibly talented illustrators who can 
                  produce stunning bespoke artwork to suit your needs. We will be guided by your vision 
                  to create something truly unique.
                </p>
                <CTAButton>COVER GALORE</CTAButton>
              </div>
              <div className="flex-shrink-0 ml-8">
                <img src={coverBooks} alt="Book covers showcase" className="w-96 h-auto" />
              </div>
            </div>
          </div>
        </section>

        {/* Layout Design Section */}
        <section id="layout-design" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <div className="bg-primary text-primary-foreground py-8 px-8 flex items-center justify-between">
              <div className="flex-1">
                <h2 className="text-4xl font-bold mb-4">STUNNING BOOK PAGE</h2>
                <h2 className="text-4xl font-bold mb-6">LAYOUT DESIGN</h2>
                <p className="mb-4 max-w-2xl">
                  No matter how complex, we offer a full range of options to produce creative page 
                  layout designs and stunning looking books.
                </p>
                <p className="mb-4 max-w-2xl">
                  We believe that your book deserves only the very best when it comes to design.
                </p>
                <p className="mb-8 max-w-2xl">
                  Our mission is to create a book you'll love, one that appeals to your audience, and 
                  is a cut above the competition. With your unique content, and our book design expertise, 
                  we will ensure that the finished product is something that you can be proud of.
                </p>
                <CTAButton>RECENT PROJECTS</CTAButton>
              </div>
              <div className="flex-shrink-0 ml-8">
                <img src={layoutBooks} alt="Book layout examples" className="w-96 h-auto" />
              </div>
            </div>
          </div>
        </section>

        {/* Illustrations Section */}
        <section id="illustrations" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <div className="bg-primary text-primary-foreground py-8 px-8 flex items-center justify-between">
              <div className="flex-1">
                <h2 className="text-4xl font-bold mb-4">LIVELY ILLUSTRATIONS...</h2>
                <h2 className="text-4xl font-bold mb-6">VIVID COLOURING</h2>
                <p className="mb-4 max-w-2xl">
                  It's our passion for creating beautifully finished illustrations that enables us to 
                  create books that are head and shoulders above the rest.
                </p>
                <p className="mb-8 max-w-2xl">
                  For an extra special touch, we work with incredibly talented illustrators who can 
                  produce stunning and bespoke artwork to suit your needs. We will be guided by your 
                  vision to create something truly unique.
                </p>
                <CTAButton>ART GALLERY</CTAButton>
              </div>
              <div className="flex-shrink-0 ml-8">
                <img src={illustrations} alt="Illustration samples" className="w-96 h-auto" />
              </div>
            </div>
          </div>
        </section>

        {/* Galore Section */}
        <section id="galore" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <div className="bg-primary text-primary-foreground py-16 px-8">
              <h2 className="text-5xl font-bold text-center mb-12">THE GALORE TOUR</h2>
              <div className="flex items-center justify-center gap-8">
                <div className="text-4xl font-bold text-black leading-tight text-center">
                  <div>Random</div>
                  <div>Slide</div>
                  <div>Show</div>
                  <div>Our</div>
                  <div>Work</div>
                </div>
                <div className="bg-white text-primary rounded-lg p-8 w-48 text-center">
                  <h3 className="text-2xl font-bold mb-2">Cover</h3>
                  <h3 className="text-2xl font-bold">Design</h3>
                </div>
                <div className="bg-white text-primary rounded-lg p-8 w-48 text-center">
                  <h3 className="text-2xl font-bold mb-2">Layout</h3>
                  <h3 className="text-2xl font-bold">Design</h3>
                </div>
                <div className="bg-white text-primary rounded-lg p-8 w-48 text-center">
                  <h3 className="text-2xl font-bold mb-2">Illustrations</h3>
                  <h3 className="text-2xl font-bold">&</h3>
                  <h3 className="text-2xl font-bold">Colouring</h3>
                </div>
                <div className="text-4xl font-bold text-black leading-tight text-center">
                  <div>Random</div>
                  <div>Slide</div>
                  <div>Show</div>
                  <div>Our</div>
                  <div>Work</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Corporate Design Section */}
        <section id="corporate-design" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <div className="bg-primary text-primary-foreground py-8 px-8">
              <h2 className="text-4xl font-bold mb-2">CREATIVE</h2>
              <h2 className="text-5xl font-bold mb-8">CORPORATE DESIGNING</h2>
              
              <div className="flex gap-12 mb-8">
                <div className="flex-1">
                  <h3 className="text-2xl font-bold mb-4">DESIGN VALUE</h3>
                  <p className="mb-4">
                    We are strongly positioned to capitalise on the convergence of data, media, insights 
                    and technology to revolutionise how brands connect with consumers. This passion 
                    resonates in how we work together with our clients to drive change and build their 
                    businesses.
                  </p>
                  <p className="mb-4">
                    We work closely with our reputed clients on a year-round tailored program, as follows:
                  </p>
                  <ul className="space-y-2 list-disc list-inside">
                    <li>Ad Campaign</li>
                    <li>Brand Identity</li>
                    <li>Business Cards</li>
                    <li>Stationary Design</li>
                    <li>Packaging Design</li>
                    <li>Magazines and Journals</li>
                    <li>Annual Reports</li>
                  </ul>
                </div>
                
                <div className="flex-1">
                  <h3 className="text-2xl font-bold mb-4">LOGO STRATEGY</h3>
                  <p className="mb-8">
                    Creating distinctive brand identities that resonate with your target audience.
                  </p>
                  
                  <h3 className="text-2xl font-bold mb-4">ADVERTISING MARKETING</h3>
                  <p>
                    Strategic campaigns that drive engagement and deliver measurable results.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Reach Us Section */}
        <section id="reach-us" className="max-w-7xl mx-auto px-8 mb-16">
          <div className="border-4 border-primary">
            <SectionHeader title="Reach Us" />
            <div className="p-12 bg-white text-center">
              <h3 className="text-3xl font-bold text-foreground mb-4">Get In Touch</h3>
              <p className="text-xl text-muted-foreground mb-8">
                Ready to bring your vision to life? Contact NE Graphics today!
              </p>
              <p className="text-lg text-foreground">
                Let's create something amazing together.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Index;
